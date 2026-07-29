"""RunPod Pod proxy의 공개 HTTP 인증 계약을 검증한다."""

from __future__ import annotations

import http.client
import importlib.util
import sys
import threading
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


def _health_status(handler: type, authorization: str | None = None) -> int:
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        headers = {"Authorization": authorization} if authorization else {}
        connection.request("GET", "/health", headers=headers)
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        thread.join(timeout=3)
        server.server_close()


def test_pod_health_rejects_requests_without_worker_api_key(
    pod_handler: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBED_API_KEY", "embed-secret")

    assert _health_status(pod_handler) == 401


def test_pod_health_accepts_requests_with_worker_api_key(
    pod_handler: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBED_API_KEY", "embed-secret")

    assert _health_status(pod_handler, "Bearer embed-secret") == 200
