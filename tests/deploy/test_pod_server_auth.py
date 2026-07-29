"""RunPod Pod proxy의 공개 HTTP 인증 계약을 검증한다."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy/runpod_worker/pod_server.py"


@pytest.fixture
def pod_handler(monkeypatch: pytest.MonkeyPatch):
    fake_service = ModuleType("service")
    fake_service.handle_input = lambda _payload: {"ok": True}
    monkeypatch.setitem(sys.modules, "service", fake_service)

    spec = importlib.util.spec_from_file_location("pod_server_auth", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PodRequestHandler


def _authorized(handler: type, authorization: str | None = None) -> bool:
    instance = object.__new__(handler)
    instance.headers = {"Authorization": authorization} if authorization else {}
    return instance._authorized()


def test_pod_health_rejects_requests_without_worker_api_key(
    pod_handler: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBED_API_KEY", "embed-secret")

    assert _authorized(pod_handler) is False


def test_pod_health_accepts_requests_with_worker_api_key(
    pod_handler: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBED_API_KEY", "embed-secret")

    assert _authorized(pod_handler, "Bearer embed-secret") is True
