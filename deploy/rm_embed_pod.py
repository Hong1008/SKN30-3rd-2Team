#!/usr/bin/env python3
"""명시 Pod ID 또는 Parameter Store 상태로 Embedder Pod을 삭제한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

if __package__:
    from .deploy_embed_pod import (
        DEFAULT_GPU,
        DEFAULT_NAME,
        LOCAL_KEYS,
        PREFIX,
        TEMPLATE_ID,
        OwnershipError,
        PodNotFoundError,
        _assert_owned,
        _describe,
        _discover_by_name,
        _local_state,
        _print,
        _runpod_env,
    )
else:
    from deploy_embed_pod import (
        DEFAULT_GPU,
        DEFAULT_NAME,
        LOCAL_KEYS,
        PREFIX,
        TEMPLATE_ID,
        OwnershipError,
        PodNotFoundError,
        _assert_owned,
        _describe,
        _discover_by_name,
        _local_state,
        _print,
        _runpod_env,
    )


def _state(environment: str) -> dict[str, str]:
    names = [
        f"{PREFIX.format(environment=environment)}/{key}"
        for key in ("pod-id", "base-url", "template-id", "name", "gpu-id")
    ]
    try:
        result = subprocess.run(
            ["aws", "ssm", "get-parameters", "--names", *names, "--output", "json"],
            check=True,
            capture_output=True,
            text=True,
        )
        body = json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise RuntimeError("AWS Parameter Store의 Embed Pod 상태를 읽지 못했습니다.") from error
    return {
        item["Name"].rsplit("/", 1)[-1]: item["Value"]
        for item in body.get("Parameters", [])
    }


def _clear_local_state() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    keys = set(LOCAL_KEYS.values())
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(
        "\n".join(line for line in lines if line.partition("=")[0].strip() not in keys) + "\n",
        encoding="utf-8",
    )


def _not_found(result: subprocess.CompletedProcess[str]) -> bool:
    return "not found" in f"{result.stdout}\n{result.stderr}".lower()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pod-id")
    parser.add_argument("--state-backend", choices=("local", "aws"), default="local")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--template-id", default=TEMPLATE_ID)
    parser.add_argument("--gpu", default=DEFAULT_GPU)
    parser.add_argument("--output", choices=("text", "json"), default="json")
    parser.add_argument("--ignore-not-found", action="store_true")
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    try:
        state = (
            {}
            if args.no_env_file
            else (
                _state(args.environment)
                if args.state_backend == "aws"
                else _local_state()
            )
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    runpodctl = shutil.which("runpodctl")
    if not runpodctl:
        print("runpodctl 실행 파일을 찾을 수 없습니다.", file=sys.stderr)
        return 2

    pod_id = args.pod_id or state.get("pod-id")
    expected_name = state.get("name") or args.name
    expected_template = state.get("template-id") or args.template_id
    expected_gpu = state.get("gpu-id") or args.gpu
    pod = None
    if not pod_id:
        try:
            pod = _discover_by_name(runpodctl, expected_name)
        except (OwnershipError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
        if pod is None:
            output = {
                "pod_id": None,
                "status": "ABSENT",
                "owned": False,
                "deleted": False,
            }
            _print(output, args.output, "삭제할 Embed Pod가 없습니다.")
            return 0
        try:
            pod_id = _pod_id(pod)
        except OwnershipError as error:
            print(str(error), file=sys.stderr)
            return 1

    try:
        pod = pod or _describe(runpodctl, pod_id)
        identity = _assert_owned(
            pod,
            pod_id=pod_id,
            name=expected_name,
            template_id=expected_template,
            gpu=expected_gpu,
        )
    except PodNotFoundError as error:
        if not args.ignore_not_found:
            print(str(error), file=sys.stderr)
            return 1
        try:
            _clear_state(
                args.state_backend,
                args.environment,
                no_env_file=args.no_env_file,
            )
        except RuntimeError as clear_error:
            print(str(clear_error), file=sys.stderr)
            return 1
        output = {
            "pod_id": pod_id,
            "status": "NOT_FOUND",
            "owned": False,
            "deleted": False,
        }
        _print(output, args.output, f"Pod가 이미 없습니다: {pod_id}")
        return 0
    except (OwnershipError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    if args.status:
        output = {
            "pod_id": pod_id,
            "status": identity["status"],
            "owned": True,
            "deleted": False,
        }
        _print(output, args.output, f"Pod 상태: {identity['status']}")
        return 0

    if args.dry_run:
        output = {
            "pod_id": pod_id,
            "status": identity["status"],
            "owned": True,
            "deleted": False,
            "action": "delete",
            "dry_run": True,
        }
        _print(output, args.output, f"Pod 삭제 예정: {pod_id}")
        return 0

    result = subprocess.run(
        [runpodctl, "pod", "delete", pod_id],
        capture_output=True,
        text=True,
        env=_runpod_env(),
    )
    if result.returncode and not (args.ignore_not_found and _not_found(result)):
        print(result.stderr or result.stdout, file=sys.stderr)
        return result.returncode
    try:
        _clear_state(
            args.state_backend,
            args.environment,
            no_env_file=args.no_env_file,
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    output = {
        "pod_id": pod_id,
        "status": identity["status"],
        "owned": True,
        "deleted": result.returncode == 0,
    }
    _print(output, args.output, f"Pod 삭제 완료: {pod_id}")
    return 0


def _pod_id(pod: dict[str, object]) -> str:
    value = pod.get("id") or pod.get("podId")
    if not value:
        raise OwnershipError("재발견한 Embed Pod 응답에 ID가 없습니다.")
    return str(value)


def _clear_state(
    state_backend: str,
    environment: str,
    *,
    no_env_file: bool = False,
) -> None:
    if no_env_file:
        return
    if state_backend == "aws":
        for key in (
            "pod-id",
            "base-url",
            "template-id",
            "name",
            "gpu-id",
            "last-provision-run-id",
        ):
            result = subprocess.run(
                [
                    "aws",
                    "ssm",
                    "delete-parameter",
                    "--name",
                    f"{PREFIX.format(environment=environment)}/{key}",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode and "not found" not in f"{result.stdout}\n{result.stderr}".lower():
                raise RuntimeError(f"Parameter Store 상태를 지우지 못했습니다: {key}")
    else:
        _clear_local_state()


if __name__ == "__main__":
    raise SystemExit(main())
