"""실험별 설정으로 재사용하는 결정론적 평가 거버넌스 게이트."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ExperimentConfig:
    """실험마다 달라지는 값만 보관하는 동결 설정."""

    experiment_id: str
    version: str
    baseline_commit: str
    tuning_count: int
    heldout_count: int
    tuning_max_fn: int
    tuning_max_fp: int
    tuning_min_f1: float
    heldout_max_fn: int
    heldout_max_fp: int
    heldout_min_f1: float
    contract_type: str | None = None
    topic_group_field: str = "topic_group"
    enforce_topic_groups: bool = True


def sha256_file(path: str | Path) -> str:
    """파일의 SHA-256을 계산합니다."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | Path) -> dict[str, Any]:
    """held-out manifest의 기본 구조를 검증합니다."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = payload.get("heldout_case_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(item, str) for item in ids):
        raise ValueError(f"held-out manifest 형식 오류: {path}")
    if len(set(ids)) != len(ids):
        raise ValueError("held-out manifest에 중복 case_id가 있습니다.")
    return payload


def split_cases(
    cases: list[dict[str, Any]], manifest: dict[str, Any], config: ExperimentConfig,
) -> dict[str, list[dict[str, Any]]]:
    """manifest와 topic group을 함께 사용해 tuning/held-out을 분리합니다."""
    heldout_ids = set(manifest["heldout_case_ids"])
    case_ids = [case.get("case_id") for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("골든 케이스에 중복 case_id가 있습니다.")
    unknown = heldout_ids - set(case_ids)
    if unknown:
        raise ValueError(f"held-out manifest에 없는 case_id가 있습니다: {sorted(unknown)}")
    if config.contract_type is not None:
        wrong = [case["case_id"] for case in cases if case.get("contract_type") != config.contract_type]
        if wrong:
            raise ValueError(f"실험 대상 계약유형이 아닌 케이스가 섞였습니다: {wrong[:3]}")
    result = {
        "tuning": [case for case in cases if case["case_id"] not in heldout_ids],
        "held-out": [case for case in cases if case["case_id"] in heldout_ids],
    }
    if (len(result["tuning"]) != config.tuning_count or
            len(result["held-out"]) != config.heldout_count):
        raise ValueError(
            f"{config.experiment_id} 분할 수가 잘못되었습니다: "
            f"tuning={len(result['tuning'])}, held-out={len(result['held-out'])}"
        )
    if not config.enforce_topic_groups:
        return result
    groups: dict[tuple[Any, Any], set[str]] = {}
    for case in cases:
        group = case.get(config.topic_group_field)
        if not isinstance(group, str) or not group.strip():
            raise ValueError(f"case_id {case.get('case_id')!r}의 topic group이 비어 있습니다.")
        key = (case.get("contract_type"), group)
        groups.setdefault(key, set()).add("held-out" if case["case_id"] in heldout_ids else "tuning")
    leaked = [key for key, splits in groups.items() if len(splits) > 1]
    if leaked:
        raise ValueError(f"topic group split 누출: {leaked}")
    return result


def passed(scores: dict[str, float | int], config: ExperimentConfig, split: str) -> bool:
    """사전 승인된 FN/FP/F1 조건을 결정론적으로 판정합니다."""
    if split == "tuning":
        return scores["fn"] <= config.tuning_max_fn and scores["fp"] <= config.tuning_max_fp and scores["f1"] > config.tuning_min_f1
    if split == "held-out":
        return scores["fn"] <= config.heldout_max_fn and scores["fp"] <= config.heldout_max_fp and scores["f1"] > config.heldout_min_f1
    raise ValueError("split은 tuning 또는 held-out이어야 합니다.")


def validate_approval(
    approval: dict[str, Any], *, config: ExperimentConfig, manifest_sha256: str,
    tuning_report_sha256: str, runtime_tree_sha: str, allowed_split: str = "held-out",
) -> None:
    """승인 파일이 실험 설정·입력 해시·런타임 코드 트리와 일치하는지 검증합니다.

    approval 파일을 커밋하면 HEAD 자체는 바뀌므로, 전체 커밋 해시 대신 ``HEAD:src`` Git tree
    해시를 비교한다. 문서·승인 파일만 커밋한 경우는 허용하고 런타임 코드를 바꾼 경우는 막는다.
    """
    required = {"experiment_id", "baseline_commit", "runtime_tree_sha", "manifest_sha256", "tuning_report_sha256", "approved_by", "approved_at", "allowed_split"}
    missing = required - approval.keys()
    if missing:
        raise ValueError(f"승인 파일 필드 누락: {sorted(missing)}")
    if approval["experiment_id"] != config.experiment_id:
        raise ValueError("승인 파일의 experiment_id가 실험 설정과 다릅니다.")
    if approval["allowed_split"] != allowed_split:
        raise ValueError("승인 파일이 held-out 실행을 허용하지 않습니다.")
    if not approval["approved_by"] or not approval["approved_at"]:
        raise ValueError("승인자와 승인 시각은 비어 있을 수 없습니다.")
    if approval["baseline_commit"] != config.baseline_commit:
        raise ValueError("승인 파일의 기준선 커밋이 동결 설정과 다릅니다.")
    if approval["manifest_sha256"] != manifest_sha256 or approval["tuning_report_sha256"] != tuning_report_sha256:
        raise ValueError("승인 파일과 입력 산출물 해시가 다릅니다.")
    if approval["runtime_tree_sha"] != runtime_tree_sha:
        raise ValueError("승인 파일과 현재 런타임 코드 트리 해시가 다릅니다.")


def validate_approval_repository_state(approval_path: str | Path, *, repo_root: str | Path, baseline_commit: str) -> None:
    """승인 파일 추적·커밋, clean worktree, 기준선 커밋 존재를 확인합니다."""
    root, path = Path(repo_root).resolve(), Path(approval_path).resolve()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("승인 파일은 저장소 안에 있어야 합니다.") from exc
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=root, capture_output=True, text=True)
    if tracked.returncode != 0:
        raise ValueError("승인 파일이 git에 추적되고 있지 않습니다.")
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture_output=True, text=True, check=True)
    if status.stdout.strip():
        raise ValueError("held-out 실행 전 작업 트리가 깨끗해야 합니다.")
    for command in (["git", "diff", "--quiet", "HEAD", "--", rel], ["git", "diff", "--cached", "--quiet", "HEAD", "--", rel]):
        if subprocess.run(command, cwd=root, capture_output=True).returncode != 0:
            raise ValueError("승인 파일에 커밋되지 않은 변경이 있습니다.")
    if subprocess.run(["git", "cat-file", "-e", f"{baseline_commit}^{{commit}}"], cwd=root, capture_output=True).returncode != 0:
        raise ValueError("동결 기준선 커밋을 저장소에서 찾을 수 없습니다.")


def reserve_run_record(path: str | Path, payload: dict[str, Any]) -> None:
    """O_EXCL로 실행 기록을 원자적으로 선점합니다."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise ValueError(f"실험 실행 기록이 이미 존재합니다: {destination}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
    except Exception:
        try: destination.unlink()
        except FileNotFoundError: pass
        raise


def update_run_record(path: str | Path, updates: dict[str, Any]) -> None:
    """실행 기록을 임시 파일 교체로 원자 갱신합니다."""
    destination = Path(path)
    payload = json.loads(destination.read_text(encoding="utf-8")); payload.update(updates)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True); stream.write("\n"); temporary = Path(stream.name)
    os.replace(temporary, destination)


def build_confusion_summary(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """outcome 행으로 혼동행렬과 F1을 계산합니다."""
    counts = {key: 0 for key in ("tp", "fp", "fn", "tn")}
    for row in rows: counts[row["outcome"].lower()] += 1
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return {**counts, "precision": p, "recall": r, "f1": 2*p*r/(p+r) if p+r else 0.0}
