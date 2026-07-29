"""Embed Pod lifecycle의 소유권 판정을 외부 CLI 없이 검증한다."""

import os

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
