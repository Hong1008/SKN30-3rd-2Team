#!/usr/bin/env python3
"""Embedder·Reranker Pod을 멱등 생성하고 안전한 상태만 반환한다."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

TEMPLATE_ID = "maqkz41mly"
DEFAULT_GPU = "NVIDIA RTX 2000 Ada"
DEFAULT_NAME = "workshield-prod-embed"
HTTP_USER_AGENT = "workshield-infra/1.0"
RUNPOD_REST_API = "https://rest.runpod.io/v1"
PREFIX = "/workshield/{environment}/runpod/embed"
LOCAL_KEYS = {
    "pod-id": "RUNPOD_EMBED_POD_ID",
    "base-url": "RUNPOD_POD_BASE_URL",
    "api-key": "RUNPOD_EMBED_API_KEY",
    "template-id": "RUNPOD_EMBED_POD_TEMPLATE_ID",
    "name": "RUNPOD_EMBED_POD_NAME",
    "gpu-id": "RUNPOD_EMBED_POD_GPU_ID",
}


class PodNotFoundError(RuntimeError):
    """조회 대상 Pod가 이미 사라진 경우다."""


class OwnershipError(RuntimeError):
    """조회된 Pod가 이 스크립트의 관리 대상임을 확인하지 못한 경우다."""


def _aws(args: list[str]) -> str:
    return subprocess.run(["aws", *args], check=True, capture_output=True, text=True).stdout.strip()


def _state(environment: str) -> dict[str, str]:
    names = [
        f"{PREFIX.format(environment=environment)}/{key}"
        for key in (
            "pod-id",
            "base-url",
            "template-id",
            "name",
            "gpu-id",
            "last-provision-run-id",
        )
    ]
    try:
        body = json.loads(_aws(["ssm", "get-parameters", "--names", *names, "--output", "json"]))
    except (json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise RuntimeError("AWS Parameter Store의 Embed Pod 상태를 읽지 못했습니다.") from error
    return {item["Name"].rsplit("/", 1)[-1]: item["Value"] for item in body.get("Parameters", [])}


def _put_state(values: dict[str, str], environment: str) -> None:
    for key, value in values.items():
        _aws(["ssm", "put-parameter", "--name", f"{PREFIX.format(environment=environment)}/{key}", "--value", value, "--type", "String", "--overwrite"])


def _local_update(values: dict[str, str]) -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition("=")[0].strip() not in values]
    path.write_text("\n".join([*lines, *(f"{k}='{v}'" for k, v in values.items())]) + "\n", encoding="utf-8")


def _local_state() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return {}
    values = {
        key.strip(): value.strip().strip("'\"")
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
        for key, _, value in (line.partition("="),)
    }
    pod_id = values.get(LOCAL_KEYS["pod-id"], "")
    if not pod_id:
        return {}
    return {
        state_key: values.get(env_key, "")
        for state_key, env_key in LOCAL_KEYS.items()
    }


def _existing_state(
    *,
    no_env_file: bool,
    state_backend: str,
    environment: str,
) -> dict[str, str]:
    if no_env_file:
        return {}
    return (
        _state(environment)
        if state_backend == "aws"
        else _local_state()
    )


def _run_json_value(command: list[str]) -> Any:
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=_runpod_env() if Path(command[0]).name.startswith("runpodctl") else None,
    )
    try:
        body = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"명령의 JSON 응답을 해석하지 못했습니다: {' '.join(command[:3])}") from error
    return body


def _run_json(command: list[str]) -> dict[str, Any]:
    body = _run_json_value(command)
    if not isinstance(body, dict):
        raise RuntimeError("RunPod CLI 응답이 JSON 객체가 아닙니다.")
    return body


def _runpod_env() -> dict[str, str]:
    """부모 저장소의 관리 키 명칭을 runpodctl 전용 명칭으로만 변환한다."""
    environment = os.environ.copy()
    management_key = environment.get("RUNPOD_MANAGEMENT_API_KEY")
    if management_key:
        environment["RUNPOD_API_KEY"] = management_key
    return environment


def _delete_created_pod(runpodctl: str, pod_id: str) -> None:
    subprocess.run(
        [runpodctl, "pod", "delete", pod_id],
        capture_output=True,
        text=True,
        env=_runpod_env(),
    )


def _not_found(error: subprocess.CalledProcessError) -> bool:
    return "not found" in f"{error.stdout}\n{error.stderr}".lower()


def _describe(runpodctl: str, pod_id: str) -> dict[str, Any]:
    if _management_key():
        body = _rest_json(f"/pods/{urllib.parse.quote(pod_id, safe='')}")
        if not isinstance(body, dict):
            raise RuntimeError("RunPod REST Pod 상세 응답이 객체가 아닙니다.")
        return body
    try:
        return _run_json([runpodctl, "pod", "get", pod_id, "-o", "json"])
    except subprocess.CalledProcessError as error:
        if _not_found(error):
            raise PodNotFoundError(f"RunPod Pod를 찾을 수 없습니다: {pod_id}") from error
        raise RuntimeError(f"RunPod Pod 조회에 실패했습니다: {pod_id}") from error


def _pod_items(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict):
        for key in ("pods", "items", "data"):
            items = body.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    raise RuntimeError("RunPod Pod 목록 응답 형식을 해석하지 못했습니다.")


def _discover_by_name(runpodctl: str, name: str) -> dict[str, Any] | None:
    """로컬 상태가 없어도 결정적 이름으로 관리 대상을 재발견한다."""
    try:
        body = (
            _rest_json("/pods")
            if _management_key()
            else _run_json_value([runpodctl, "pod", "list", "-o", "json"])
        )
        items = _pod_items(body)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("RunPod Pod 목록 조회에 실패했습니다.") from error
    matches = [
        pod for pod in items
        if _pod_identity(pod)["name"] == name
    ]
    if len(matches) > 1:
        raise OwnershipError(f"동일한 이름의 Embed Pod가 여러 개입니다: {name}")
    return matches[0] if matches else None


def _value(body: dict[str, Any], *paths: tuple[str, ...]) -> str:
    for path in paths:
        value: Any = body
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _management_key() -> str:
    return (
        os.getenv("RUNPOD_MANAGEMENT_API_KEY")
        or os.getenv("RUNPOD_API_KEY")
        or ""
    )


def _rest_json(path: str) -> Any:
    management_key = _management_key()
    if not management_key:
        raise RuntimeError("RunPod REST 조회에는 관리 API key가 필요합니다.")
    request = urllib.request.Request(
        f"{RUNPOD_REST_API}{path}",
        headers={
            "Authorization": f"Bearer {management_key}",
            "Accept": "application/json",
            "User-Agent": HTTP_USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise PodNotFoundError(path) from error
        raise RuntimeError(
            f"RunPod REST 조회 실패: HTTP {error.code}, path={path}"
        ) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"RunPod REST 조회 실패: path={path}") from error


def _pod_identity(pod: dict[str, Any]) -> dict[str, str]:
    """runpodctl 버전별 응답 차이를 흡수해 소유권 필드를 추출한다."""
    return {
        "pod-id": _value(pod, ("id",), ("podId",)),
        "name": _value(pod, ("name",), ("podName",)),
        "template-id": _value(
            pod,
            ("templateId",),
            ("template", "id"),
            ("template", "templateId"),
        ),
        "gpu-id": _value(
            pod,
            ("gpuDisplayName",),
            ("gpuTypeId",),
            ("gpuType",),
            ("machine", "gpuDisplayName"),
            ("machine", "gpuTypeId"),
        ),
        "status": _value(pod, ("desiredStatus",), ("status",)).upper(),
    }


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _same_gpu(actual: str, expected: str) -> bool:
    actual_value = _normalized(actual).replace("nvidia", "").replace("generation", "")
    expected_value = _normalized(expected).replace("nvidia", "").replace("generation", "")
    return bool(actual_value and expected_value and actual_value == expected_value)


def _assert_owned(
    pod: dict[str, Any],
    *,
    pod_id: str,
    name: str,
    template_id: str,
    gpu: str,
) -> dict[str, str]:
    """API 조회 결과의 immutable 필드가 원하는 대상과 모두 일치하는지 확인한다."""
    identity = _pod_identity(pod)
    mismatches: list[str] = []
    if identity["pod-id"] != pod_id:
        mismatches.append(f"pod-id={identity['pod-id'] or '<unknown>'}")
    if identity["name"] != name:
        mismatches.append(f"name={identity['name'] or '<unknown>'}")
    if identity["template-id"] != template_id:
        mismatches.append(f"template-id={identity['template-id'] or '<unknown>'}")
    if identity["gpu-id"] and not _same_gpu(identity["gpu-id"], gpu):
        mismatches.append(f"gpu-id={identity['gpu-id'] or '<unknown>'}")
    if mismatches:
        raise OwnershipError(
            "Embed Pod 소유권 또는 immutable 설정을 확인하지 못했습니다: "
            + ", ".join(mismatches)
        )
    return identity


def _wait(base_url: str, api_key: str, timeout: int) -> None:
    endpoint = f"{base_url}/health"
    started_at = time.monotonic()
    deadline = started_at + timeout
    delay = 2.0
    last_status = "endpoint 연결 대기"
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "User-Agent": HTTP_USER_AGENT,
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    anonymous = urllib.request.Request(
                        endpoint,
                        headers={
                            "Accept": "application/json",
                            "User-Agent": HTTP_USER_AGENT,
                        },
                    )
                    try:
                        with urllib.request.urlopen(anonymous, timeout=10):
                            pass
                    except urllib.error.HTTPError as error:
                        if error.code in (401, 403):
                            detail = error.read(256).decode(
                                "utf-8",
                                "replace",
                            ).strip()
                            if "error code: 1010" in detail:
                                raise RuntimeError(
                                    "RunPod proxy가 무인증 health check를 "
                                    "Cloudflare 1010으로 차단했습니다."
                                ) from error
                            return
                        last_status = f"무인증 요청 HTTP {error.code}"
                        raise
                    raise RuntimeError("Embedder 무인증 요청이 허용되었습니다.")
        except urllib.error.HTTPError as error:
            detail = error.read(256).decode("utf-8", "replace").strip()
            if error.code in (401, 403) and "error code: 1010" in detail:
                raise RuntimeError(
                    "RunPod proxy가 health check 요청을 Cloudflare 1010으로 "
                    "차단했습니다."
                ) from error
            if error.code in (401, 403):
                raise RuntimeError(
                    f"Embedder 인증 요청이 HTTP {error.code}으로 거부되었습니다."
                ) from error
            last_status = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError) as error:
            last_status = str(error) or type(error).__name__
        elapsed = int(time.monotonic() - started_at)
        print(
            f"Embedder readiness 대기 중: {elapsed}s, 최근 상태={last_status}",
            file=sys.stderr,
        )
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(delay * 1.5, 15.0)
    raise TimeoutError(
        f"Embedder Pod readiness timeout: {timeout}s, 최근 상태={last_status}"
    )


def _print(output: dict[str, Any], output_format: str, message: str) -> None:
    print(json.dumps(output, ensure_ascii=False) if output_format == "json" else message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pod-id", help="상태 backend 대신 검증하거나 재사용할 Pod ID")
    parser.add_argument("--gpu", default=DEFAULT_GPU)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--state-backend", choices=("local", "aws"), default="local")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--template-id", default=TEMPLATE_ID)
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="부모 orchestrator가 검증된 candidate를 만들 때만 사용하는 옵션",
    )
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    runpodctl = shutil.which("runpodctl")
    if not runpodctl:
        print("runpodctl 실행 파일을 찾을 수 없습니다.", file=sys.stderr)
        return 2
    try:
        existing = _existing_state(
            no_env_file=args.no_env_file,
            state_backend=args.state_backend,
            environment=args.environment,
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.pod_id:
        existing["pod-id"] = args.pod_id
    expected_name = existing.get("name") or args.name
    expected_template = existing.get("template-id") or args.template_id
    expected_gpu = existing.get("gpu-id") or args.gpu
    api_key = os.getenv("RUNPOD_EMBED_API_KEY") or existing.get("api-key", "")

    pod: dict[str, Any] | None = None
    identity: dict[str, str] | None = None
    if existing.get("pod-id"):
        try:
            pod = _describe(runpodctl, existing["pod-id"])
            identity = _assert_owned(
                pod,
                pod_id=existing["pod-id"],
                name=expected_name,
                template_id=expected_template,
                gpu=expected_gpu,
            )
        except PodNotFoundError:
            pod = None
        except (OwnershipError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
    if pod is None:
        try:
            discovered = _discover_by_name(runpodctl, expected_name)
            if discovered is not None:
                discovered_id = _pod_identity(discovered)["pod-id"]
                identity = _assert_owned(
                    discovered,
                    pod_id=discovered_id,
                    name=expected_name,
                    template_id=expected_template,
                    gpu=expected_gpu,
                )
                existing["pod-id"] = discovered_id
                existing.setdefault(
                    "base-url",
                    f"https://{discovered_id}-8000.proxy.runpod.net",
                )
                pod = discovered
        except (OwnershipError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
    if identity is not None and not existing.get("base-url"):
        existing["base-url"] = (
            f"https://{existing['pod-id']}-8000.proxy.runpod.net"
        )

    if args.status:
        output = {
            "pod_id": existing.get("pod-id"),
            "base_url": existing.get("base-url", ""),
            "name": expected_name,
            "template_id": expected_template,
            "gpu": expected_gpu,
            "status": identity["status"] if identity else "NOT_FOUND",
            "owned": identity is not None,
            "created": False,
        }
        _print(output, args.output, f"Pod 상태: {output['status']}")
        return 0

    if identity is not None and not args.replace:
        if identity["status"] != "RUNNING":
            print(
                f"기존 Embed Pod가 RUNNING 상태가 아닙니다: {identity['status'] or '<unknown>'}",
                file=sys.stderr,
            )
            return 1
        if args.wait and not args.dry_run:
            if not api_key:
                print("기존 Embedder Pod readiness 확인에 RUNPOD_EMBED_API_KEY가 필요합니다.", file=sys.stderr)
                return 2
            try:
                _wait(existing.get("base-url", ""), api_key, args.timeout_seconds)
            except Exception:
                print("기존 Embedder Pod가 readiness 검증을 통과하지 못했습니다.", file=sys.stderr)
                return 1
        output = {
            "pod_id": existing["pod-id"],
            "base_url": existing.get("base-url", ""),
            "model_id": "embed-rerank",
            "name": expected_name,
            "template_id": expected_template,
            "gpu": expected_gpu,
            "status": identity["status"],
            "created": False,
            "action": "reuse",
            "dry_run": args.dry_run,
        }
        _print(output, args.output, f"기존 Pod 재사용: {output['pod_id']}")
        return 0

    if args.dry_run:
        output = {
            "pod_id": None,
            "base_url": "",
            "model_id": "embed-rerank",
            "name": args.name,
            "template_id": args.template_id,
            "gpu": args.gpu,
            "status": "ABSENT",
            "created": False,
            "action": "replace" if args.replace and identity is not None else "create",
            "dry_run": True,
        }
        _print(output, args.output, f"Pod 생성 예정: {args.name}")
        return 0

    if args.no_env_file and not api_key:
        print(
            "--no-env-file 모드에서는 RUNPOD_EMBED_API_KEY를 환경변수로 제공해야 합니다.",
            file=sys.stderr,
        )
        return 2

    api_key = api_key or secrets.token_hex(32)
    pod_id: str | None = None
    try:
        body = _run_json(
            [
                runpodctl,
                "pod",
                "create",
                "--template-id",
                args.template_id,
                "--gpu-id",
                args.gpu,
                "--name",
                args.name,
                "--env",
                json.dumps({"EMBED_API_KEY": api_key}),
                "-o",
                "json",
            ]
        )
        pod_id = str(body["id"])
        base_url = f"https://{pod_id}-8000.proxy.runpod.net"
        described = _describe(runpodctl, pod_id)
        identity = _assert_owned(
            described,
            pod_id=pod_id,
            name=args.name,
            template_id=args.template_id,
            gpu=args.gpu,
        )
        if args.wait:
            _wait(base_url, api_key, args.timeout_seconds)
        values = {
            "pod-id": pod_id,
            "base-url": base_url,
            "template-id": args.template_id,
            "name": args.name,
            "gpu-id": args.gpu,
            "last-provision-run-id": os.getenv("GITHUB_RUN_ID", "manual"),
        }
        if args.state_backend == "aws":
            _put_state(values, args.environment)
        elif not args.no_env_file:
            _local_update(
                {
                    LOCAL_KEYS["pod-id"]: pod_id,
                    LOCAL_KEYS["base-url"]: base_url,
                    LOCAL_KEYS["api-key"]: api_key,
                    LOCAL_KEYS["template-id"]: args.template_id,
                    LOCAL_KEYS["name"]: args.name,
                    LOCAL_KEYS["gpu-id"]: args.gpu,
                }
            )
        output = {
            "pod_id": pod_id,
            "base_url": base_url,
            "model_id": "embed-rerank",
            "name": args.name,
            "template_id": args.template_id,
            "gpu": args.gpu,
            "status": identity["status"],
            "created": True,
            "action": "replace" if args.replace else "create",
            "dry_run": False,
        }
        _print(output, args.output, f"Pod 생성 완료: {pod_id}")
        return 0
    except subprocess.CalledProcessError as error:
        if pod_id:
            _delete_created_pod(runpodctl, pod_id)
        detail = (error.stderr or error.stdout or "").strip()
        if detail:
            print(detail, file=sys.stderr)
        print("Embedder Pod 생성 실패", file=sys.stderr)
        return 1
    except Exception as error:
        if pod_id:
            _delete_created_pod(runpodctl, pod_id)
        print(str(error), file=sys.stderr)
        print("Embedder Pod 생성 실패", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
