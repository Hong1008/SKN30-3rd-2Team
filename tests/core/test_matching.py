"""core.select_best_match 규격 테스트.

select_best_match는 임계값 판정을 하지 않는다 — 점수가 낮아도 최고점 후보를 그대로
반환한다(EXTRA/NONE 판정은 classify_clause_deviation이 match_threshold로 확정).
"""
from contracts.enums import ContractType, Category
from contracts.models import StandardClause
from core import select_best_match


def _std(clause_id: str) -> StandardClause:
    """테스트용 표준조항 생성 헬퍼."""
    return StandardClause(
        clause_id=clause_id, contract_type=ContractType.SW_FREELANCE,
        category=Category.IP_OWNERSHIP, title="t", text="본문",
        source="src", version="2020",
    )


def test_빈_후보는_매칭없음():
    assert select_best_match([]) == (None, 0.0)


def test_최고점수_후보를_선택():
    a, b = _std("a"), _std("b")
    best, score = select_best_match([(a, 0.3), (b, 0.9)])
    assert best.clause_id == "b"
    assert score == 0.9


def test_임계치_미만이어도_최고점_후보를_반환():
    """점수가 낮아도 후보 자체는 그대로 돌려준다 — 임계값 판정은 이 함수의 책임이 아니다."""
    a = _std("a")
    best, score = select_best_match([(a, 0.4)])
    assert best.clause_id == "a"
    assert score == 0.4
