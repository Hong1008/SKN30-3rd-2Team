"""실험 S의 결정론적 분할·승인·단회 실행 게이트."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from eval.experiment_governance import (
    ExperimentConfig as _ExperimentConfig,
    build_confusion_summary as _generic_build_confusion_summary,
    load_manifest as _generic_load_manifest,
    reserve_run_record as _generic_reserve_run_record,
    sha256_file as _generic_sha256_file,
    split_cases as _generic_split_cases,
    update_run_record as _generic_update_run_record,
    validate_approval as _generic_validate_approval,
    validate_approval_repository_state as _generic_validate_approval_repository_state,
)


EXPERIMENT_ID = "S"
VERSION = "v4"
# v4 기준선은 실험 S 구현 직전의 동결 커밋이다.
BASELINE_COMMIT = "001fed3f98bb218e16bd910fa41ee2ee9cd5174c"
TUNING_COUNT = 36
HELDOUT_COUNT = 18
TUNING_MAX_FN = 7
TUNING_MAX_FP = 5
TUNING_MIN_F1 = 0.563
HELDOUT_MAX_FN = 6
HELDOUT_MAX_FP = 1
HELDOUT_MIN_F1 = 0.364

_S_CONFIG = _ExperimentConfig(
    experiment_id=EXPERIMENT_ID, version=VERSION, baseline_commit=BASELINE_COMMIT,
    tuning_count=TUNING_COUNT, heldout_count=HELDOUT_COUNT,
    tuning_max_fn=TUNING_MAX_FN, tuning_max_fp=TUNING_MAX_FP, tuning_min_f1=TUNING_MIN_F1,
    heldout_max_fn=HELDOUT_MAX_FN, heldout_max_fp=HELDOUT_MAX_FP, heldout_min_f1=HELDOUT_MIN_F1,
    enforce_topic_groups=False,
)


def sha256_file(path: str | Path) -> str:
    """파일의 SHA-256을 계산합니다."""
    return _generic_sha256_file(path)


def load_manifest(path: str | Path) -> dict[str, Any]:
    """실험 매니페스트를 읽고 기본 구조를 검증합니다."""
    return _generic_load_manifest(path)


def split_cases(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """manifest 순서를 보존하며 tuning/held-out을 분리합니다."""
    return _generic_split_cases(cases, manifest, _S_CONFIG)


def tuning_passed(scores: dict[str, float | int]) -> bool:
    """실험 카드의 tuning 통과 조건을 판정합니다."""
    return (
        scores["fn"] <= TUNING_MAX_FN
        and scores["fp"] <= TUNING_MAX_FP
        and scores["f1"] > TUNING_MIN_F1
    )


def heldout_passed(scores: dict[str, float | int]) -> bool:
    """실험 카드의 held-out 채택 조건을 판정합니다."""
    return (
        scores["fn"] <= HELDOUT_MAX_FN
        and scores["fp"] <= HELDOUT_MAX_FP
        and scores["f1"] > HELDOUT_MIN_F1
    )


def validate_approval(
    approval: dict[str, Any], *, manifest_sha256: str, tuning_report_sha256: str,
    runtime_tree_sha: str, allowed_split: str = "held-out",
    expected_baseline_commit: str | None = None,
) -> None:
    """사전 승인 파일이 현재 실행 입력과 정확히 일치하는지 검증합니다."""
    config = _S_CONFIG if expected_baseline_commit is not None else replace(
        _S_CONFIG, baseline_commit=approval.get("baseline_commit", "")
    )
    _generic_validate_approval(
        approval, config=config, manifest_sha256=manifest_sha256,
        tuning_report_sha256=tuning_report_sha256, runtime_tree_sha=runtime_tree_sha,
        allowed_split=allowed_split,
    )


def validate_approval_repository_state(
    approval_path: str | Path, *, repo_root: str | Path = ".",
) -> None:
    """승인 파일이 git에 추적·커밋되어 있고 작업 트리가 깨끗한지 검증합니다."""
    _generic_validate_approval_repository_state(
        approval_path, repo_root=repo_root, baseline_commit=BASELINE_COMMIT
    )


def reserve_run_record(path: str | Path, payload: dict[str, Any]) -> None:
    """평가 전에 O_EXCL로 단회 실행 예약을 원자적으로 생성합니다."""
    return _generic_reserve_run_record(path, payload)


def update_run_record(path: str | Path, updates: dict[str, Any]) -> None:
    """예약 기록의 상태를 원자적으로 갱신합니다. 기록 파일은 삭제하지 않습니다."""
    return _generic_update_run_record(path, updates)


def ensure_case_ids_allowed(
    case_ids: set[str] | None, *, heldout_ids: set[str], split: str | None,
) -> None:
    """임의 case ID로 held-out을 우회하거나 split과 혼용하는 것을 차단합니다."""
    if case_ids and case_ids & heldout_ids:
        raise ValueError("held-out case_id는 --case-ids로 지정할 수 없습니다.")
    if split is not None and case_ids is not None:
        raise ValueError("실험 S에서는 --split과 --case-ids를 함께 사용할 수 없습니다.")


def validate_run_record_absent(path: str | Path) -> None:
    """동일 held-out 실행 기록이 있으면 단회 보호를 위해 중단합니다."""
    if Path(path).exists():
        raise ValueError(f"held-out 실행 기록이 이미 존재합니다: {path}")


def build_confusion_summary(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """진단 행에서 결정론적인 혼동행렬과 F1을 계산합니다."""
    return _generic_build_confusion_summary(rows)


def build_top3_diff(before_rows: list[dict[str, Any]], after_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """case_id 기준으로 독소 top-3 및 rerank_text 차이를 정렬해 만듭니다."""
    before = {row["case_id"]: row for row in before_rows}
    after = {row["case_id"]: row for row in after_rows}
    diff = []
    for case_id in sorted(set(before) | set(after)):
        old = before.get(case_id, {})
        new = after.get(case_id, {})
        old_candidates = old.get("top_candidates", [])
        new_candidates = new.get("top_candidates", [])
        if old_candidates != new_candidates:
            diff.append({
                "case_id": case_id,
                "before_top3": old_candidates,
                "after_top3": new_candidates,
                "score_diff": [
                    {
                        "before": old_item.get("score"),
                        "after": new_item.get("score"),
                        "delta": (float(new_item.get("score", 0.0)) - float(old_item.get("score", 0.0))),
                    }
                    for old_item, new_item in zip(old_candidates, new_candidates)
                ],
                "rerank_text_changed": [
                    (item.get("pattern_id"), item.get("rerank_text"))
                    for item in new_candidates
                    if item.get("rerank_text") is not None
                ],
            })
    return diff
