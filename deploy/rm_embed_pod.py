#!/usr/bin/env python3
"""Delete the configured embedding/reranker RunPod Pod."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path


MCP_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = MCP_ROOT / ".env"
ENV_KEYS = ("RUNPOD_EMBED_POD_ID", "RUNPOD_POD_BASE_URL")


def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.lstrip().startswith("#"):
            values[key.strip()] = value.strip().strip("'\"")
    return values


def pod_id_from_url(url: str) -> str:
    match = re.match(r"https?://([A-Za-z0-9]+)-8000\.proxy\.runpod\.net/?$", url)
    return match.group(1) if match else ""


def remove_env_keys() -> None:
    if not ENV_FILE.exists():
        return
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line.partition("=")[0].strip() not in ENV_KEYS]
    ENV_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")


def main() -> int:
    values = read_env()
    pod_id = values.get("RUNPOD_EMBED_POD_ID") or pod_id_from_url(values.get("RUNPOD_POD_BASE_URL", ""))
    if not pod_id:
        print("mcp/.env에 RUNPOD_EMBED_POD_ID 또는 RUNPOD_POD_BASE_URL가 없습니다. 삭제할 Pod가 없습니다.")
        return 0

    runpodctl = shutil.which("runpodctl")
    if not runpodctl:
        print("runpodctl을 찾을 수 없습니다. `just install-runpod`으로 설치·인증하세요.", file=sys.stderr)
        return 2

    command = [runpodctl, "pod", "delete", pod_id]
    print("Executing:", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        print(f"Pod 삭제에 실패했습니다: {error}", file=sys.stderr)
        return error.returncode or 1

    remove_env_keys()
    print(f"Pod 삭제 완료: {pod_id}")
    print("mcp/.env에서 RUNPOD_EMBED_POD_ID와 RUNPOD_POD_BASE_URL를 제거했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
