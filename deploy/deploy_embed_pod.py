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
from pathlib import Path
from typing import Any

TEMPLATE_ID = "maqkz41mly"
DEFAULT_GPU = "NVIDIA RTX 2000 Ada"
PREFIX = "/workshield/{environment}/runpod/embed"


def _aws(args: list[str]) -> str:
    return subprocess.run(["aws", *args], check=True, capture_output=True, text=True).stdout.strip()


def _state(environment: str) -> dict[str, str]:
    names = [f"{PREFIX.format(environment=environment)}/{key}" for key in ("pod-id", "base-url", "template-id", "last-provision-run-id")]
    try:
        body = json.loads(_aws(["ssm", "get-parameters", "--names", *names, "--output", "json"]))
    except subprocess.CalledProcessError:
        return {}
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
    pod_id = values.get("RUNPOD_EMBED_POD_ID", "")
    if not pod_id:
        return {}
    return {
        "pod-id": pod_id,
        "base-url": values.get("RUNPOD_POD_BASE_URL", ""),
        "api-key": values.get("RUNPOD_EMBED_API_KEY", ""),
    }


def _run_json(command: list[str]) -> dict[str, Any]:
    return json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)


def _usable(runpodctl: str, pod_id: str) -> bool:
    try:
        pod = _run_json([runpodctl, "pod", "get", pod_id, "-o", "json"])
        status = str(pod.get("desiredStatus") or pod.get("status") or "").upper()
        return status == "RUNNING"
    except Exception:
        return False


def _wait(base_url: str, api_key: str, timeout: int) -> None:
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout
    delay = 2.0
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(f"{base_url}/health", headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    try:
                        urllib.request.urlopen(f"{base_url}/health", timeout=10)
                    except urllib.error.HTTPError as error:
                        if error.code in (401, 403):
                            return
                        raise RuntimeError(f"Embedder 무인증 요청이 {error.code}으로 거부되었습니다.") from error
                    raise RuntimeError("Embedder 무인증 요청이 허용되었습니다.")
        except Exception:
            time.sleep(delay)
            delay = min(delay * 2, 15)
    raise TimeoutError("Embedder Pod readiness timeout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", default=DEFAULT_GPU)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--state-backend", choices=("local", "aws"), default="local")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--name", default="workshield-prod-embed")
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    runpodctl = shutil.which("runpodctl")
    if not runpodctl:
        return 2
    existing = _state(args.environment) if args.state_backend == "aws" else _local_state()
    api_key = os.getenv("RUNPOD_EMBED_API_KEY") or existing.get("api-key", "")
    if existing.get("pod-id") and _usable(runpodctl, existing["pod-id"]):
        if args.wait:
            if not api_key:
                print("기존 Embedder Pod readiness 확인에 RUNPOD_EMBED_API_KEY가 필요합니다.", file=sys.stderr)
                return 2
            try:
                _wait(existing.get("base-url", ""), api_key, args.timeout_seconds)
            except Exception:
                print("기존 Embedder Pod가 readiness 검증을 통과하지 못했습니다.", file=sys.stderr)
                return 1
        output = {"pod_id": existing["pod-id"], "base_url": existing.get("base-url", ""), "model_id": "embed-rerank", "created": False}
        print(json.dumps(output) if args.output == "json" else f"기존 Pod 재사용: {output['pod_id']}")
        return 0
    api_key = api_key or secrets.token_hex(32)
    pod_id: str | None = None
    try:
        body = _run_json([runpodctl, "pod", "create", "--template-id", TEMPLATE_ID, "--gpu-id", args.gpu, "--name", args.name, "--env", json.dumps({"EMBED_API_KEY": api_key}), "-o", "json"])
        pod_id = str(body["id"])
        base_url = f"https://{pod_id}-8000.proxy.runpod.net"
        if args.wait:
            _wait(base_url, api_key, args.timeout_seconds)
        values = {
            "pod-id": pod_id,
            "base-url": base_url,
            "template-id": TEMPLATE_ID,
            "last-provision-run-id": os.getenv("GITHUB_RUN_ID", "manual"),
        }
        if args.state_backend == "aws":
            _put_state(values, args.environment)
        elif not args.no_env_file:
            _local_update({"RUNPOD_EMBED_POD_ID": pod_id, "RUNPOD_POD_BASE_URL": base_url, "RUNPOD_EMBED_API_KEY": api_key})
        output = {"pod_id": pod_id, "base_url": base_url, "model_id": "embed-rerank", "created": True}
        print(json.dumps(output) if args.output == "json" else f"Pod 생성 완료: {pod_id}")
        return 0
    except Exception:
        if pod_id:
            subprocess.run([runpodctl, "pod", "delete", pod_id], capture_output=True, text=True)
        print("Embedder Pod 생성 실패", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
