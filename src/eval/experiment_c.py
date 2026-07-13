"""v5 SW OVER_MATCH 실험 C의 설정·진단·승인 규격."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from eval.experiment_governance import (
    ExperimentConfig, build_confusion_summary, load_manifest, passed, sha256_file,
    split_cases, validate_approval, validate_approval_repository_state,
    reserve_run_record, update_run_record,
)

EXPERIMENT_C = ExperimentConfig(
    experiment_id="C", version="v5", baseline_commit="6c3c8602d0a9d78188a9c5f33ffaba627df99af4",
    tuning_count=30, heldout_count=15,
    tuning_max_fn=8, tuning_max_fp=2, tuning_min_f1=0.653,
    heldout_max_fn=3, heldout_max_fp=1, heldout_min_f1=0.653,
    contract_type="SW_FREELANCE",
)

GOLDEN_DIR = Path("src/eval/golden")
MANIFEST_PATH = GOLDEN_DIR / "threshold_heldout.v5.json"
CASE_MATRIX_PATH = GOLDEN_DIR / "v5_sw_case_matrix.json"
BASELINE_DIAGNOSTICS_PATH = GOLDEN_DIR / "v5_diagnostics.json"
BASELINE_PATH = Path("docs/experiments/C/baseline.json")


def validate_baseline_inputs(path: str | Path = BASELINE_PATH) -> dict[str, Any]:
    """기준선에 기록된 입력 파일 해시가 현재 파일과 일치하는지 검증합니다."""
    baseline_path = Path(path)
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    files = {
        "golden": Path("src/eval/golden/v5_sw_freelance.json"),
        "case_matrix": CASE_MATRIX_PATH,
        "heldout_manifest": MANIFEST_PATH,
        "diagnostics": BASELINE_DIAGNOSTICS_PATH,
    }
    expected = payload.get("files_sha256")
    if not isinstance(expected, dict):
        raise ValueError("C baseline.json에 files_sha256가 없습니다.")
    for key, file_path in files.items():
        if not file_path.exists():
            raise ValueError(f"C 기준선 입력 파일이 없습니다: {file_path}")
        actual = sha256_file(file_path)
        if expected.get(key) != actual:
            raise ValueError(f"C 기준선 입력 해시가 다릅니다: {key}")
    return payload


def split_sw_cases(cases: list[dict[str, Any]], manifest: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """SW 45건을 topic group 누출 없이 30/15건으로 나눕니다."""
    matrix = {row["case_id"]: row for row in json.loads(CASE_MATRIX_PATH.read_text(encoding="utf-8"))} if CASE_MATRIX_PATH.exists() else {}
    enriched = [{**case, **{key: matrix.get(case["case_id"], {}).get(key) for key in ("topic_group", "split")}} for case in cases]
    source = manifest or load_manifest(MANIFEST_PATH)
    case_ids = {case["case_id"] for case in enriched}
    sw_manifest = {**source, "heldout_case_ids": [case_id for case_id in source["heldout_case_ids"] if case_id in case_ids]}
    return split_cases(enriched, sw_manifest, EXPERIMENT_C)


def is_overmatch(row: dict[str, Any]) -> bool:
    """C 실험에서 고정한 OVER_MATCH 정의입니다."""
    return row.get("gold_deviation") == "EXTRA" and row.get("predicted_deviation") == "NONE"


def classify_overmatch(rows: list[dict[str, Any]], matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """tuning OVER_MATCH만 결정론적으로 진단 축별로 펼칩니다."""
    by_id = {row["case_id"]: row for row in matrix}
    result = []
    for row in rows:
        if not is_overmatch(row):
            continue
        candidates = row.get("top_candidates") or []
        top = candidates[0] if candidates else {}
        second = candidates[1] if len(candidates) > 1 else {}
        top_score = float(top.get("score", 0.0)); second_score = float(second.get("score", 0.0))
        result.append({
            "case_id": row["case_id"],
            "contract_type": row.get("contract_type"),
            "contrast_clause_id": by_id.get(row["case_id"], {}).get("contrast_clause_id"),
            "top1_score": top_score, "top2_score": second_score,
            "top1_top2_gap": top_score - second_score,
            "trap": by_id.get(row["case_id"], {}).get("trap", row.get("trap", "none")),
            "candidate_source": top.get("source", "NONE"),
            "candidate_parent_clause_id": top.get("parent_clause_id"),
            "topic_group": by_id.get(row["case_id"], {}).get("topic_group"),
            "matched_standard_id": (row.get("matched_standard") or {}).get("id"),
            "confidence": float(row.get("confidence", 0.0)),
        })
    return sorted(result, key=lambda item: item["case_id"])


def taxonomy_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """오류 축별 빈도를 집계합니다. 해석 문장을 생성하지 않습니다."""
    return {field: dict(Counter(row.get(field) for row in rows)) for field in (
        "contrast_clause_id", "trap", "candidate_source", "candidate_parent_clause_id", "topic_group",
    )}


def write_taxonomy(path: str | Path, rows: list[dict[str, Any]]) -> str:
    """사람이 검토할 수 있는 C 오류 taxonomy를 생성합니다."""
    summary = taxonomy_summary(rows)
    lines = ["# C — SW OVER_MATCH taxonomy", "", "> tuning의 OVER_MATCH만 기록합니다. held-out 진단은 이 문서 작성에 사용하지 않습니다.", "", f"- 표본 수: {len(rows)}", "- 정의: `gold_deviation=EXTRA`이고 `predicted_deviation=NONE`", ""]
    for field, values in summary.items():
        lines += [f"## {field}", "", "| 값 | 건수 |", "| --- | ---: |"]
        lines += [f"| {key} | {count} |" for key, count in sorted(values.items(), key=lambda item: (-item[1], str(item[0])))]
        lines.append("")
    lines += ["## 사례", "", "| case_id | contrast | top1-top2 gap | trap | source |", "| --- | --- | ---: | --- | --- |"]
    lines += [f"| {r['case_id']} | {r['contrast_clause_id']} | {r['top1_top2_gap']:.6f} | {r['trap']} | {r['candidate_source']} |" for r in rows]
    destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True); destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(destination)


def validate_c_approval(approval: dict[str, Any], *, manifest_sha256: str, tuning_report_sha256: str, code_commit: str) -> None:
    """C 전용 설정으로 공통 승인 게이트를 적용합니다."""
    validate_approval(approval, config=EXPERIMENT_C, manifest_sha256=manifest_sha256, tuning_report_sha256=tuning_report_sha256, code_commit=code_commit)


__all__ = ["EXPERIMENT_C", "MANIFEST_PATH", "CASE_MATRIX_PATH", "BASELINE_DIAGNOSTICS_PATH", "BASELINE_PATH", "split_sw_cases", "is_overmatch", "classify_overmatch", "taxonomy_summary", "write_taxonomy", "validate_baseline_inputs", "validate_c_approval"]
