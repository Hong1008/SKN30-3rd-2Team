"""Embed Pod lifecycle의 소유권 판정을 외부 CLI 없이 검증한다."""

import io
import os
import urllib.error

import pytest

from deploy import deploy_embed_pod as lifecycle
from deploy import rm_embed_pod
from deploy.deploy_embed_pod import (
    OwnershipError,
    _assert_owned,
    _pod_identity,
    _runpod_env,
)


def test_pod_identity_accepts_expected_immutable_configuration() -> None:
    pod = {
        "id": "pod-123",
        "name": "workshield-prod-embed",
        "templateId": "maqkz41mly",
        "machine": {"gpuDisplayName": "NVIDIA RTX 2000 Ada Generation"},
        "desiredStatus": "RUNNING",
    }

    identity = _assert_owned(
        pod,
        pod_id="pod-123",
        name="workshield-prod-embed",
        template_id="maqkz41mly",
        gpu="NVIDIA RTX 2000 Ada",
    )

    assert identity["status"] == "RUNNING"


def test_pod_identity_accepts_rest_response_without_gpu_name() -> None:
    identity = _assert_owned(
        {
            "id": "pod-123",
            "name": "workshield-prod-embed",
            "templateId": "maqkz41mly",
            "desiredStatus": "RUNNING",
        },
        pod_id="pod-123",
        name="workshield-prod-embed",
        template_id="maqkz41mly",
        gpu="NVIDIA RTX 2000 Ada",
    )

    assert identity["gpu-id"] == ""
    assert identity["status"] == "RUNNING"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "someone-elses-pod"),
        ("templateId", "other-template"),
        ("gpuDisplayName", "NVIDIA RTX A5000"),
    ],
)
def test_pod_identity_rejects_unknown_ownership_or_immutable_drift(
    field: str,
    value: str,
) -> None:
    pod = {
        "id": "pod-123",
        "name": "workshield-prod-embed",
        "templateId": "maqkz41mly",
        "gpuDisplayName": "NVIDIA RTX 2000 Ada",
        "desiredStatus": "RUNNING",
    }
    pod[field] = value

    with pytest.raises(OwnershipError):
        _assert_owned(
            pod,
            pod_id="pod-123",
            name="workshield-prod-embed",
            template_id="maqkz41mly",
            gpu="NVIDIA RTX 2000 Ada",
        )


def test_pod_identity_supports_nested_runpod_response_fields() -> None:
    identity = _pod_identity(
        {
            "podId": "pod-123",
            "podName": "workshield-prod-embed",
            "template": {"id": "maqkz41mly"},
            "machine": {"gpuTypeId": "NVIDIA RTX A5000"},
            "status": "running",
        }
    )

    assert identity == {
        "pod-id": "pod-123",
        "name": "workshield-prod-embed",
        "template-id": "maqkz41mly",
        "gpu-id": "NVIDIA RTX A5000",
        "status": "RUNNING",
    }


def test_management_key_is_mapped_only_for_runpodctl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNPOD_MANAGEMENT_API_KEY", "management-secret")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    environment = _runpod_env()

    assert environment["RUNPOD_API_KEY"] == "management-secret"
    assert os.getenv("RUNPOD_API_KEY") is None


def test_discovery_rejects_duplicate_deterministic_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lifecycle,
        "_run_json_value",
        lambda _command: [
            {"id": "pod-1", "name": "workshield-prod-embed"},
            {"id": "pod-2", "name": "workshield-prod-embed"},
        ],
    )

    with pytest.raises(OwnershipError, match="여러 개"):
        lifecycle._discover_by_name("runpodctl", "workshield-prod-embed")


def test_parent_removal_mode_does_not_clear_standalone_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> None:
        raise AssertionError("standalone .env를 변경하면 안 됩니다.")

    monkeypatch.setattr(rm_embed_pod, "_clear_local_state", fail_if_called)

    rm_embed_pod._clear_state("local", "prod", no_env_file=True)


def test_parent_deploy_mode_can_skip_standalone_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> dict[str, str]:
        raise AssertionError("standalone .env를 읽으면 안 됩니다.")

    monkeypatch.setattr(lifecycle, "_local_state", fail_if_called)

    existing = lifecycle._existing_state(
        no_env_file=True,
        state_backend="local",
        environment="prod",
    )

    assert existing == {}


class _Response:
    status = 200

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_embed_health_uses_user_agent_and_requires_anonymous_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def urlopen(request: object, timeout: int) -> _Response:
        requests.append(request)
        if request.get_header("Authorization"):  # type: ignore[attr-defined]
            return _Response()
        raise urllib.error.HTTPError(
            "https://pod/health",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":"Unauthorized"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    lifecycle._wait("https://pod", "embed-key", 1)

    assert len(requests) == 2
    assert all(
        request.get_header("User-agent") == "workshield-infra/1.0"  # type: ignore[attr-defined]
        for request in requests
    )
