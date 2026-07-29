"""Pod·Serverless 경로의 인증 책임 분리를 검증한다."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "src/adapter/api_embedding_model.py"


@pytest.fixture
def api_embedding_model() -> ModuleType:
    spec = importlib.util.spec_from_file_location("api_embedding_model_headers", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_pod_proxy_uses_dedicated_embedder_api_key(
    api_embedding_model: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_embedding_model, "RUNPOD_POD_BASE_URL", "https://pod.example")
    monkeypatch.setattr(api_embedding_model, "RUNPOD_EMBED_API_KEY", "embed-secret")

    assert api_embedding_model._headers() == {
        "Authorization": "Bearer embed-secret",
        "Content-Type": "application/json",
    }


def test_local_pod_proxy_requires_dedicated_embedder_api_key(
    api_embedding_model: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_embedding_model, "RUNPOD_POD_BASE_URL", "https://pod.example")
    monkeypatch.setattr(api_embedding_model, "RUNPOD_EMBED_API_KEY", None)

    with pytest.raises(RuntimeError, match="RUNPOD_EMBED_API_KEY"):
        api_embedding_model._headers()


def test_serverless_keeps_runpod_api_key_authentication(
    api_embedding_model: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_embedding_model, "RUNPOD_POD_BASE_URL", None)
    monkeypatch.setattr(api_embedding_model, "RUNPOD_API_KEY", "runpod-secret")

    assert api_embedding_model._headers() == {
        "Authorization": "Bearer runpod-secret",
        "Content-Type": "application/json",
    }
