#!/usr/bin/env python3
"""RunPod Pod용 임베딩·리랭커 이미지와 Pod 생명주기를 관리한다."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final


MCP_ROOT: Final = Path(__file__).resolve().parents[2]
ENV_FILE: Final = MCP_ROOT / ".env"
DEFAULTS: Final = {
    "RUNPOD_EMBED_POD_TEMPLATE_NAME": "workshield-embed-rerank-pod",
    "RUNPOD_EMBED_POD_NAME": "workshield-embed-rerank-pod",
    "RUNPOD_EMBED_POD_GPU_ID": "NVIDIA RTX A5000",
    "RUNPOD_EMBED_POD_CLOUD_TYPE": "COMMUNITY",
    "RUNPOD_EMBED_POD_CONTAINER_DISK_GB": "25",
}


def load_environment() -> None:
    """mcp/.env의 RUNPOD_* 값만 현재 환경에 없는 경우에 적용한다."""
    if not ENV_FILE.exists():
        return
    for line_number, raw_line in enumerate(ENV_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        if not separator or not key.startswith("RUNPOD_"):
            continue
        try:
            parsed = shlex.split(value.strip(), posix=True)
        except ValueError as error:
            raise ValueError(f"{ENV_FILE}:{line_number}의 RUNPOD 환경변수 형식이 올바르지 않습니다.") from error
        os.environ.setdefault(key, "" if not parsed else parsed[0])


def setting(name: str, *, required: bool = False) -> str:
    value = os.getenv(name, DEFAULTS.get(name, "")).strip()
    if required and not value:
        raise ValueError(f"{name}이 필요합니다. {ENV_FILE}에 설정하세요.")
    return value


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise RuntimeError(f"{command}을 찾을 수 없습니다. 설치 후 PATH에 추가하세요.")


def display_command(command: list[str]) -> str:
    """POD_API_KEY가 담긴 JSON 환경변수는 출력할 때만 마스킹한다."""
    displayed = command.copy()
    for index, item in enumerate(displayed):
        if "POD_API_KEY" in item:
            displayed[index] = '{"POD_API_KEY":"***"}'
    return shlex.join(displayed)


def redact_output(value: object) -> object:
    """CLI JSON의 API key·token 계열 필드는 화면 출력 전에 마스킹한다."""
    if isinstance(value, dict):
        return {
            key: "***" if any(marker in key.upper() for marker in ("KEY", "TOKEN", "PASSWORD", "SECRET")) else redact_output(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_output(item) for item in value]
    return value


def display_output(output: str) -> str:
    try:
        return json.dumps(redact_output(json.loads(output)), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return output


def run(command: list[str], *, confirm: bool) -> str:
    print(display_command(command))
    if not confirm:
        return ""
    result = subprocess.run(command, check=True, capture_output=True, text=True, env=os.environ.copy())
    if result.stdout.strip():
        print(display_output(result.stdout.strip()))
    return result.stdout


def resource_id(output: str, resource: str) -> str | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    for field in ("id", f"{resource}Id", f"{resource}_id"):
        value = payload.get(field)
        if isinstance(value, str) and value:
            return value
    nested = payload.get(resource)
    if isinstance(nested, dict) and isinstance(nested.get("id"), str):
        return nested["id"]
    return None


def template_command() -> list[str]:
    return [
        "runpodctl", "template", "create",
        "--name", setting("RUNPOD_EMBED_POD_TEMPLATE_NAME"),
        "--image", setting("RUNPOD_EMBED_POD_IMAGE"),
        "--ports", "8000/http",
        "--container-disk-in-gb", setting("RUNPOD_EMBED_POD_CONTAINER_DISK_GB"),
        "--env", json.dumps({"POD_API_KEY": setting("RUNPOD_POD_API_KEY", required=True)}),
        "--readme", "WorkShield embedding/rerank Pod. POST /runsync with the Serverless-compatible request envelope.",
    ]


def pod_command() -> list[str]:
    command = [
        "runpodctl", "pod", "create",
        "--template-id", setting("RUNPOD_EMBED_POD_TEMPLATE_ID", required=True),
        "--name", setting("RUNPOD_EMBED_POD_NAME"),
        "--gpu-id", setting("RUNPOD_EMBED_POD_GPU_ID"),
        "--cloud-type", setting("RUNPOD_EMBED_POD_CLOUD_TYPE"),
        "--gpu-count", "1",
        "--ssh=false",
    ]
    registry_auth_id = setting("RUNPOD_EMBED_POD_REGISTRY_AUTH_ID")
    if registry_auth_id:
        command.extend(["--registry-auth-id", registry_auth_id])
    return command


def pod_id() -> str:
    return setting("RUNPOD_EMBED_POD_ID", required=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "push", "template-create", "template-info", "gpu-list", "pod-create", "pod-list", "pod-info", "pod-stop", "pod-delete"))
    parser.add_argument("--confirm", action="store_true", help="외부 상태를 변경하는 명령을 실제 실행합니다.")
    args = parser.parse_args()
    load_environment()

    try:
        if args.action in {"build", "push"}:
            require_command("docker")
            image = setting("RUNPOD_EMBED_POD_IMAGE")
            command = (["docker", "build", "--platform", "linux/amd64", "-f", "deploy/runpod_worker/Pod.Dockerfile", "-t", image, "."] if args.action == "build" else ["docker", "push", image])
            run(command, confirm=args.confirm)
            return 0

        require_command("runpodctl")
        if args.action in {"template-create", "pod-create", "pod-stop", "pod-delete"}:
            setting("RUNPOD_API_KEY", required=True)
        if args.action == "template-create":
            template_id = resource_id(run(template_command(), confirm=args.confirm), "template")
            if template_id:
                print(f"\n생성된 Template ID: {template_id}")
                print("mcp/.env의 RUNPOD_EMBED_POD_TEMPLATE_ID에 직접 기록하세요.")
            return 0
        if args.action == "template-info":
            run(["runpodctl", "template", "get", setting("RUNPOD_EMBED_POD_TEMPLATE_ID", required=True)], confirm=True)
            return 0
        if args.action == "gpu-list":
            run(["runpodctl", "gpu", "list"], confirm=True)
            return 0
        if args.action == "pod-create":
            created_pod_id = resource_id(run(pod_command(), confirm=args.confirm), "pod")
            if created_pod_id:
                print(f"\n생성된 Pod ID: {created_pod_id}")
                print("mcp/.env의 RUNPOD_EMBED_POD_ID에 직접 기록하세요.")
                print(f"RUNPOD_POD_BASE_URL=https://{created_pod_id}-8000.proxy.runpod.net")
            return 0
        if args.action == "pod-list":
            run(["runpodctl", "pod", "list", "--all"], confirm=True)
            return 0
        if args.action == "pod-info":
            run(["runpodctl", "pod", "get", pod_id()], confirm=True)
            return 0
        if args.action == "pod-stop":
            run(["runpodctl", "pod", "stop", pod_id()], confirm=args.confirm)
            return 0
        if args.action == "pod-delete":
            run(["runpodctl", "pod", "delete", pod_id()], confirm=args.confirm)
            return 0
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        print(detail, file=sys.stderr)
        return error.returncode or 2
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
