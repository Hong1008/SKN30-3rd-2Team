"""평가 전용 case-level 후보·오류 진단 기록입니다.

동결된 MCP/계약 모델과 프로덕션 판정 경로를 바꾸지 않습니다.
"""
import json
from pathlib import Path
from typing import Any


def _value(value: Any) -> Any:
    """Enum·테스트 더블을 JSON 원시값으로 변환합니다."""
    return getattr(value, "value", value)


def _outcome(gold_positive: bool, predicted_positive: bool) -> str:
    """케이스 단위 이진 혼동행렬 결과를 반환합니다."""
    if gold_positive and predicted_positive:
        return "TP"
    if not gold_positive and predicted_positive:
        return "FP"
    if gold_positive:
        return "FN"
    return "TN"


def _toxic_candidate(hit: dict[str, Any], rank: int) -> dict[str, Any]:
    """독소 검색 후보를 출력용 필드로 축소합니다."""
    return {
        "rank": rank,
        "pattern_id": hit.get("id") or hit.get("pattern_id"),
        "pattern": _value(hit.get("pattern")),
        "category": _value(hit.get("category")),
        "text": hit.get("text"),
        "rerank_text": hit.get("rerank_text"),
        "score": float(hit.get("rerank_score", 0.0)),
    }


def _standard_candidate(hit: dict[str, Any], rank: int) -> dict[str, Any]:
    """표준·서브청크 검색 후보를 출력용 필드로 축소합니다."""
    return {
        "rank": rank,
        "standard_id": hit.get("id") or hit.get("clause_id") or hit.get("parent_clause_id"),
        "parent_clause_id": hit.get("parent_clause_id"),
        "category": _value(hit.get("category")),
        "version": hit.get("version"),
        "score": float(hit.get("rerank_score", 0.0)),
        "source": hit.get("source", "UNKNOWN"),
    }


def build_case_diagnostics(
    golden_by_type: dict[str, list[dict[str, Any]]],
    review_results_by_type: dict[str, dict[str, Any]],
    toxic_hits_by_type: dict[str, dict[str, list[dict[str, Any]]]],
    standard_hits_by_type: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    match_threshold: float = 0.5,
    toxic_threshold: float = 0.6,
) -> dict[str, list[dict[str, Any]]]:
    """이탈·독소의 top-3 후보와 FP/FN 원인 표식을 결정론적으로 만듭니다."""
    deviation_rows: list[dict[str, Any]] = []
    toxic_rows: list[dict[str, Any]] = []
    for contract_type, golden in golden_by_type.items():
        review_results = review_results_by_type[contract_type]
        for case in golden:
            case_id = case["case_id"]
            result = review_results[case_id]
            gold_deviation = case["gold_deviation"]
            predicted_deviation = _value(result.deviation)
            deviation_gold_positive = gold_deviation != "NONE"
            deviation_predicted_positive = predicted_deviation != "NONE"
            standard_candidates = [
                _standard_candidate(hit, rank)
                for rank, hit in enumerate(standard_hits_by_type[contract_type].get(case_id, [])[:3], 1)
            ]
            matched = result.matched_standard
            matched_standard = None if matched is None else {
                "id": matched.clause_id,
                "version": matched.version,
                "category": _value(matched.category),
            }
            if deviation_gold_positive and not standard_candidates:
                deviation_reason = "NO_CANDIDATE"
            elif deviation_gold_positive and not deviation_predicted_positive:
                deviation_reason = "OVER_MATCH"
            elif not deviation_gold_positive and deviation_predicted_positive:
                deviation_reason = "UNDER_MATCH"
            elif deviation_gold_positive and float(result.confidence) < match_threshold:
                deviation_reason = "BELOW_THRESHOLD"
            else:
                deviation_reason = "CORRECT"
            deviation_rows.append({
                "case_id": case_id, "contract_type": contract_type, "trap": case.get("trap", "none"),
                "gold_deviation": gold_deviation, "predicted_deviation": predicted_deviation,
                "confidence": float(result.confidence), "matched_standard": matched_standard,
                "top_candidates": standard_candidates,
                "outcome": _outcome(deviation_gold_positive, deviation_predicted_positive),
                "predicted_by_threshold": {
                    f"{threshold:.2f}": matched is None or float(result.confidence) < threshold
                    for threshold in (0.40, 0.45, 0.50, 0.55, 0.60)
                },
                "reason": deviation_reason,
            })

            gold_patterns = sorted(_value(pattern) for pattern in case.get("gold_toxic") or [])
            toxic_candidates = [
                _toxic_candidate(hit, rank)
                for rank, hit in enumerate(toxic_hits_by_type[contract_type].get(case_id, [])[:3], 1)
            ]
            predicted_patterns = sorted(_value(pattern) for pattern in result.toxic_patterns)
            toxic_gold_positive = bool(gold_patterns)
            toxic_predicted_positive = bool(predicted_patterns)
            candidate_patterns = {candidate["pattern"] for candidate in toxic_candidates}
            if toxic_gold_positive and not candidate_patterns.intersection(gold_patterns):
                toxic_reason = "SEARCH_MISS"
            elif toxic_gold_positive and not toxic_predicted_positive:
                toxic_reason = "BELOW_THRESHOLD"
            elif not toxic_gold_positive and toxic_predicted_positive:
                toxic_reason = "WRONG_PATTERN"
            elif toxic_gold_positive and not set(predicted_patterns).intersection(gold_patterns):
                toxic_reason = "WRONG_PATTERN"
            else:
                toxic_reason = "CORRECT"
            toxic_rows.append({
                "case_id": case_id, "contract_type": contract_type,
                "gold_patterns": gold_patterns, "predicted_patterns": predicted_patterns,
                "top_candidates": toxic_candidates, "threshold": toxic_threshold,
                "predicted_by_threshold": {
                    f"{threshold:.2f}": sorted({
                        candidate["pattern"] for candidate in toxic_candidates
                        if candidate["score"] >= threshold and candidate["pattern"] is not None
                    })
                    for threshold in (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)
                },
                "outcome": _outcome(toxic_gold_positive, toxic_predicted_positive),
                "reason": toxic_reason,
            })
    return {"deviation": deviation_rows, "toxic": toxic_rows}


def write_case_diagnostics(
    version: str, diagnostics: dict[str, list[dict[str, Any]]], golden_dir: str,
) -> dict[str, str]:
    """진단을 JSON 및 Markdown으로 저장하고 경로를 반환합니다."""
    base = Path(golden_dir)
    json_path = base / f"{version}_diagnostics.json"
    markdown_path = base / f"{version}_diagnostics.md"
    json_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# {version} — case-level 진단", "",
        "> eval 전용 결정론적 후보·오류 분해 기록입니다. MCP 응답이나 계약 판정에는 사용하지 않습니다.",
    ]
    for label, rows in (("이탈", diagnostics["deviation"]), ("독소", diagnostics["toxic"])):
        lines.extend(["", f"## {label} case-level 진단", "", "| case_id | 유형 | outcome | reason |", "| --- | --- | --- | --- |"])
        for row in rows:
            lines.append(f"| {row['case_id']} | {row['contract_type']} | {row['outcome']} | {row['reason']} |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}
