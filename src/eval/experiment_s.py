"""실험 S의 결정론적 분할·승인·단회 실행 게이트."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


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


def sha256_file(path: str | Path) -> str:
    """파일의 SHA-256을 계산합니다."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | Path) -> dict[str, Any]:
    """실험 매니페스트를 읽고 기본 구조를 검증합니다."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = payload.get("heldout_case_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(item, str) for item in ids):
        raise ValueError(f"held-out manifest 형식 오류: {path}")
    if len(set(ids)) != len(ids):
        raise ValueError("held-out manifest에 중복 case_id가 있습니다.")
    return payload


def split_cases(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """manifest 순서를 보존하며 tuning/held-out을 분리합니다."""
    heldout_ids = set(manifest["heldout_case_ids"])
    case_ids = {case["case_id"] for case in cases}
    unknown = heldout_ids - case_ids
    if unknown:
        raise ValueError(f"held-out manifest에 없는 case_id가 있습니다: {sorted(unknown)}")
    result = {
        "tuning": [case for case in cases if case["case_id"] not in heldout_ids],
        "held-out": [case for case in cases if case["case_id"] in heldout_ids],
    }
    if len(result["tuning"]) != TUNING_COUNT or len(result["held-out"]) != HELDOUT_COUNT:
        raise ValueError(
            f"v4 실험 S 분할 수가 잘못되었습니다: tuning={len(result['tuning'])}, "
            f"held-out={len(result['held-out'])} (기대값 {TUNING_COUNT}/{HELDOUT_COUNT})"
        )
    return result


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
    code_commit: str, allowed_split: str = "held-out",
    expected_baseline_commit: str | None = None,
) -> None:
    """사전 승인 파일이 현재 실행 입력과 정확히 일치하는지 검증합니다."""
    required = {
        "experiment_id", "baseline_commit", "code_commit", "manifest_sha256",
        "tuning_report_sha256", "approved_by", "approved_at", "allowed_split",
    }
    missing = required - approval.keys()
    if missing:
        raise ValueError(f"승인 파일 필드 누락: {sorted(missing)}")
    if approval["experiment_id"] != EXPERIMENT_ID:
        raise ValueError("승인 파일의 experiment_id가 S가 아닙니다.")
    if approval["allowed_split"] != allowed_split:
        raise ValueError("승인 파일이 held-out 실행을 허용하지 않습니다.")
    if not approval["approved_by"] or not approval["approved_at"]:
        raise ValueError("승인자와 승인 시각은 비어 있을 수 없습니다.")
    if not approval["baseline_commit"]:
        raise ValueError("기준선 커밋 식별자는 비어 있을 수 없습니다.")
    if approval["manifest_sha256"] != manifest_sha256:
        raise ValueError("승인 파일과 held-out manifest 해시가 다릅니다.")
    if approval["tuning_report_sha256"] != tuning_report_sha256:
        raise ValueError("승인 파일과 tuning 결과 해시가 다릅니다.")
    if approval["code_commit"] != code_commit:
        raise ValueError("승인 파일과 현재 코드 커밋 식별자가 다릅니다.")
    if expected_baseline_commit is not None and approval["baseline_commit"] != expected_baseline_commit:
        raise ValueError("승인 파일의 기준선 커밋이 v4 동결 기준선과 다릅니다.")


def validate_approval_repository_state(
    approval_path: str | Path, *, repo_root: str | Path = ".",
) -> None:
    """승인 파일이 git에 추적·커밋되어 있고 작업 트리가 깨끗한지 검증합니다."""
    root = Path(repo_root).resolve()
    path = Path(approval_path).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError("승인 파일은 저장소 안에 있어야 합니다.") from exc
    rel = relative.as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", rel],
        cwd=root, capture_output=True, text=True,
    )
    if tracked.returncode != 0:
        raise ValueError("승인 파일이 git에 추적되고 있지 않습니다.")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root, capture_output=True, text=True, check=True,
    )
    if status.stdout.strip():
        raise ValueError("held-out 실행 전 작업 트리가 깨끗해야 합니다.")
    for command in (["git", "diff", "--quiet", "HEAD", "--", rel],
                    ["git", "diff", "--cached", "--quiet", "HEAD", "--", rel]):
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError("승인 파일에 커밋되지 않은 변경이 있습니다.")
    baseline = subprocess.run(
        ["git", "cat-file", "-e", f"{BASELINE_COMMIT}^{{commit}}"],
        cwd=root, capture_output=True, text=True,
    )
    if baseline.returncode != 0:
        raise ValueError("v4 기준선 커밋을 저장소에서 찾을 수 없습니다.")


def reserve_run_record(path: str | Path, payload: dict[str, Any]) -> None:
    """평가 전에 O_EXCL로 단회 실행 예약을 원자적으로 생성합니다."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise ValueError(f"held-out 실행 기록 또는 예약이 이미 존재합니다: {destination}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise


def update_run_record(path: str | Path, updates: dict[str, Any]) -> None:
    """예약 기록의 상태를 원자적으로 갱신합니다. 기록 파일은 삭제하지 않습니다."""
    destination = Path(path)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload.update(updates)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, destination)


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
    counts = {key: 0 for key in ("tp", "fp", "fn", "tn")}
    for row in rows:
        counts[row["outcome"].lower()] += 1
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**counts, "precision": precision, "recall": recall, "f1": f1}


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
                "rerank_text_changed": [
                    (item.get("pattern_id"), item.get("rerank_text"))
                    for item in new_candidates
                    if item.get("rerank_text") is not None
                ],
            })
    return diff
