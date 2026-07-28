#!/usr/bin/env python3
"""Create the embedding/reranker RunPod Pod from the fixed template."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


MCP_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = MCP_ROOT / ".env"
TEMPLATE_ID = "maqkz41mly"
DEFAULT_GPU = "NVIDIA RTX 2000 Ada"


def update_env_file(updates: dict[str, str]) -> None:
    """Update or append the Pod connection settings in mcp/.env."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = set()
    result = []

    for line in lines:
        key, separator, _ = line.partition("=")
        if separator and key.strip() in updates:
            name = key.strip()
            result.append(f"{name}='{updates[name]}'")
            updated.add(name)
        else:
            result.append(line)

    for name, value in updates.items():
        if name not in updated:
            result.append(f"{name}='{value}'")

    ENV_FILE.write_text("\n".join(result) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", default=DEFAULT_GPU, help=f"RunPod GPU ID (default: {DEFAULT_GPU})")
    args = parser.parse_args()

    runpodctl = shutil.which("runpodctl")
    if not runpodctl:
        print("runpodctl을 찾을 수 없습니다. `just install-runpod`으로 설치·인증하세요.", file=sys.stderr)
        return 2

    command = [
        runpodctl,
        "pod",
        "create",
        "--template-id",
        TEMPLATE_ID,
        "--gpu-id",
        args.gpu,
        "-o",
        "json",
    ]
    print(f"Template ID: {TEMPLATE_ID}")
    print(f"GPU: {args.gpu}")
    print("Executing:", " ".join(command))

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or error.stdout.strip() or "Pod 생성에 실패했습니다.", file=sys.stderr)
        return error.returncode or 1
    except json.JSONDecodeError:
        print(f"runpodctl JSON 출력을 해석하지 못했습니다:\n{result.stdout}", file=sys.stderr)
        return 1

    pod_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(pod_id, str) or not pod_id:
        print(f"Pod ID를 찾지 못했습니다:\n{result.stdout}", file=sys.stderr)
        return 1

    base_url = f"https://{pod_id}-8000.proxy.runpod.net"
    update_env_file({"RUNPOD_EMBED_POD_ID": pod_id, "RUNPOD_POD_BASE_URL": base_url})
    print("\nPod 생성 완료")
    print(f"Pod ID: {pod_id}")
    print(f"RUNPOD_POD_BASE_URL: {base_url}")
    print("mcp/.env의 RUNPOD_EMBED_POD_ID와 RUNPOD_POD_BASE_URL를 갱신했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
