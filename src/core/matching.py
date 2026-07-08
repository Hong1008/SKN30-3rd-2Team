from typing import List, Tuple, Optional
from contracts.models import StandardClause


def select_best_match(
    candidates: List[Tuple[StandardClause, float]]
) -> Tuple[Optional[StandardClause], float]:
    """
    Chroma 하이브리드 검색이 반환한 top-k 후보 중 리랭커 점수가 가장 높은 표준조항을 선택합니다.
    이 함수는 조항 단위 검토 루프에서 리랭커 결과를 받은 직후 호출되며,
    "이 사용자 조항이 어떤 표준조항과 가장 가까운가"만 결정합니다.

    임계값 판정은 하지 않습니다 — 점수가 낮아도 최고점 후보를 그대로 반환합니다.
    "매칭으로 인정할지(EXTRA/NONE)"는 호출부(core.classify_clause_deviation)가
    match_threshold와 비교해 결정합니다. 임계 미달이어도 후보를 함께 반환하는 이유는,
    EXTRA로 판정된 조항도 2차(LLM)가 "무엇과 비교해 다른지" 판단할 근거가 필요하기 때문입니다.
    candidates가 비어 있으면 pipe 레이어에서 NO_MATCH로 처리해야 합니다(이 함수의 책임 밖).

    Args:
        candidates: 리랭커가 점수를 매긴 (표준조항, 점수) 후보 목록

    Returns:
        (최고점 표준조항, 점수) — candidates가 비어 있으면 (None, 0.0)
    """
    if not candidates:
        return None, 0.0

    return max(candidates, key=lambda c: c[1])

def roll_up_sub_chunks(
    sub_chunk_results: List[Tuple[str, float]]
) -> Tuple[Optional[str], float]:
    """
    서브청크 검색 결과 목록을 parent_clause_id 별로 그룹화하여
    각 부모의 Max Score를 계산하고, 가장 점수가 높은 부모 조항 ID와 그 점수를 반환합니다.

    Args:
        sub_chunk_results (List[Tuple[str, float]]): 서브청크 수준의 검색 및 리랭크 결과 목록.
            각 튜플은 (부모 조항 ID `parent_clause_id`, 유사도 점수 `score`)로 구성됩니다.
            예: [("sw_freelance-art58", 0.85), ("sw_freelance-art58", 0.92), ("sw_freelance-art6", 0.78)]

    Returns:
        Tuple[Optional[str], float]: 가장 높은 Max Score를 기록한 부모 조항 ID와 해당 점수의 튜플.
            - 형식: (최적의 parent_clause_id, 최고 유사도 점수)
            - 입력 결과가 비어 있거나 매칭되는 부모 조항이 없는 경우 (None, 0.0)를 반환합니다.
    """
    if not sub_chunk_results:
        return None, 0.0
        
    # parent_clause_id별 최댓값(Max Score) 집계
    parent_max_scores = {}
    for parent_id, score in sub_chunk_results:
        if parent_id not in parent_max_scores:
            parent_max_scores[parent_id] = score
        else:
            parent_max_scores[parent_id] = max(parent_max_scores[parent_id], score)
            
    if not parent_max_scores:
        return None, 0.0
        
    # 가장 높은 점수를 가진 부모 조항 선정
    best_parent_id = max(parent_max_scores, key=parent_max_scores.get)
    return best_parent_id, parent_max_scores[best_parent_id]


