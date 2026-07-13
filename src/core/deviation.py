from typing import List, Optional, Set

from contracts.enums import Deviation
from contracts.models import StandardClause


def classify_clause_deviation(
    matched_standard: Optional[StandardClause],
    score: float,
    match_threshold: float,
) -> Deviation:
    """select_best_match 결과(임계값 미적용)를 match_threshold와 비교해 EXTRA/NONE을 확정합니다.

    match_threshold 미달이어도 matched_standard는 채워져 있을 수 있습니다(select_best_match는
    항상 최고점 후보를 반환) — EXTRA로 판정돼도 2차 LLM이 "무엇과 비교해 다른지" 판단할 근거로
    matched_standard를 그대로 들고 갑니다. (내용 일치 여부 자체는 2차 LLM 몫)
    """
    if matched_standard is None:
        return Deviation.EXTRA
    return Deviation.NONE if score >= match_threshold else Deviation.EXTRA


def detect_missing_clauses(
    all_standard_clauses: List[StandardClause],
    matched_clause_ids: Set[str]
) -> List[StandardClause]:
    """
    모든 사용자 조항을 처리한 뒤 루프 종료 시점에 한 번 호출됩니다.
    classify_clause_deviation이 "내 조항이 표준의 어디에 해당하는가"를 보는 방향이라면,
    이 함수는 반대 방향으로 "표준의 어느 조항이 내 계약서에 한 번도 등장하지 않았는가"를 찾습니다.
    matched_clause_ids는 루프에서 EXTRA·NONE 판정을 받은 조항들의 clause_id 집합입니다.
    """
    missing = []
    for std in all_standard_clauses:
        if std.clause_id not in matched_clause_ids:
            missing.append(std)
    return missing
