"""KoreanLawGrounder.get_grounding 의 (category, contract_type) 쿼리 선택 규격 테스트.

docs/tasks/O_grounding_contract_type.md — SI/SM(하도급) 은 SW_FREELANCE 와 카테고리가
같아도 적용 법령이 다를 수 있어, SUBCONTRACT_CATEGORY_QUERIES 오버라이드를 우선 조회하고
없으면 CATEGORY_QUERIES(유형 무관 공용)로 폴백한다. 외부 koreanLaw MCP 호출은 mock 으로
대체해 실제 쿼리 문자열 선택 로직만 검증한다.
"""
from unittest.mock import patch

from contracts.enums import Category, ContractType
from contracts.implement.korean_law_grounder import KoreanLawGrounder


def _get_grounding(category, contract_type=None):
    grounder = KoreanLawGrounder()
    with patch("contracts.implement.korean_law_grounder.koreanLaw") as mock_law:
        mock_law.query.return_value = "본문"
        grounder.get_grounding(category, contract_type)
        return mock_law.query.call_args[0][0]


def test_SW는_공용_민법_쿼리():
    assert "민법" in _get_grounding(Category.PAYMENT, ContractType.SW_FREELANCE)


def test_SI_하도급은_오버라이드_쿼리():
    assert "하도급" in _get_grounding(Category.PAYMENT, ContractType.SI_SUBCONTRACT)


def test_SM_하도급도_동일_오버라이드():
    assert "하도급" in _get_grounding(Category.DELIVERY_INSPECTION, ContractType.SM_SUBCONTRACT)


def test_오버라이드_없는_카테고리는_SI여도_공용_폴백():
    assert "민법" in _get_grounding(Category.SCOPE_SOW, ContractType.SI_SUBCONTRACT)


def test_contract_type_생략시_기존과_동일하게_공용_쿼리():
    """하위호환: contract_type 없이 호출해도 기존 동작(공용 매핑) 그대로다."""
    assert "민법" in _get_grounding(Category.PAYMENT)


def test_GENERAL은_계약유형_무관_빈리스트():
    grounder = KoreanLawGrounder()
    with patch("contracts.implement.korean_law_grounder.koreanLaw") as mock_law:
        assert grounder.get_grounding(Category.GENERAL, ContractType.SI_SUBCONTRACT) == []
        mock_law.query.assert_not_called()


# ── 신규 카테고리(INDUSTRIAL_SAFETY/INFO_SECURITY) 및 TERMINATION/LIABILITY 오버라이드 ──

def test_WARRANTY는_공용_민법_667조():
    assert "민법" in _get_grounding(Category.WARRANTY, ContractType.SW_FREELANCE)


def test_TERMINATION은_SI_하도급_오버라이드():
    """부당한 위탁취소 금지(하도급법 8조)는 민법 673조(도급인 임의해제권)와 별개 근거다."""
    assert "하도급" in _get_grounding(Category.TERMINATION, ContractType.SI_SUBCONTRACT)


def test_TERMINATION은_SW_FREELANCE에서_공용_민법_폴백():
    assert "민법" in _get_grounding(Category.TERMINATION, ContractType.SW_FREELANCE)


def test_LIABILITY는_SM_하도급_오버라이드():
    assert "하도급" in _get_grounding(Category.LIABILITY, ContractType.SM_SUBCONTRACT)


def test_INDUSTRIAL_SAFETY는_산업안전보건법():
    assert "산업안전보건법" in _get_grounding(Category.INDUSTRIAL_SAFETY, ContractType.SI_SUBCONTRACT)


def test_INFO_SECURITY는_정보통신망법():
    assert "정보통신망" in _get_grounding(Category.INFO_SECURITY, ContractType.SM_SUBCONTRACT)


def test_무효조합_경고_출력_후에도_조회는_계속됨(capsys):
    """WORKING_HOURS는 SI_SUBCONTRACT에 유효하지 않은 카테고리 — 경고만 찍고 폴백 조회는 계속한다."""
    result = _get_grounding(Category.WORKING_HOURS, ContractType.SI_SUBCONTRACT)
    assert "근로기준법" in result
    captured = capsys.readouterr()
    assert "무효 조합" in captured.out
