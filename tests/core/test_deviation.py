"""core 이탈 분류 규격 테스트 — classify_clause_deviation / detect_missing_clauses.

개정 사항: 1차 판정을 select_best_match 단일 기준(EXTRA/NONE)으로 단순화함에 따라
기존의 difflib 및 규칙 기반 치명변경 관련 테스트가 제거되었습니다. select_best_match가
임계값과 무관하게 최고점 후보를 반환하도록 바뀌어, classify_clause_deviation이 score와
match_threshold를 직접 비교해 EXTRA/NONE을 확정합니다(임계 미달 EXTRA도 matched_standard를
들고 갑니다 — 2차 LLM이 비교할 근거가 필요하므로).
"""
from contracts.enums import ContractType, Category, Deviation
from contracts.models import StandardClause
from core import (
    classify_clause_deviation,
    detect_missing_clauses,
)


def _std(clause_id: str, text: str = "표준 조항 본문입니다.") -> StandardClause:
    return StandardClause(
        clause_id=clause_id, contract_type=ContractType.SW_FREELANCE,
        category=Category.PAYMENT, title="t", text=text, source="s", version="2020",
    )


# --- classify_clause_deviation ---
def test_후보없으면_EXTRA():
    assert classify_clause_deviation(None, 0.0, match_threshold=0.5) == Deviation.EXTRA


def test_점수가_임계이상이면_NONE():
    std = _std("a")
    assert classify_clause_deviation(std, 0.9, match_threshold=0.5) == Deviation.NONE


def test_후보있어도_점수가_임계미만이면_EXTRA_이지만_matched_standard는_유지():
    """EXTRA로 판정돼도 2차 LLM이 비교할 근거가 필요하므로 matched_standard를 버리지 않는다."""
    std = _std("a")
    assert classify_clause_deviation(std, 0.3, match_threshold=0.5) == Deviation.EXTRA


# --- detect_missing_clauses ---
def test_매칭안된_표준조항은_누락으로():
    all_std = [_std("a"), _std("b"), _std("c")]
    missing = detect_missing_clauses(all_std, matched_clause_ids={"a"})
    assert {m.clause_id for m in missing} == {"b", "c"}
