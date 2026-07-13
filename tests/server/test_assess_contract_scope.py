"""MCP 지원 범위 판별 도구의 입출력 계약 테스트."""

from unittest.mock import MagicMock, patch

from contracts.enums import ContractType
from contracts.models import Clause
from server.server import assess_contract_scope


def _clause(text: str) -> Clause:
    return Clause(idx=1, num="제1조", title="목적", text=text)


@patch("server.server.get_parser")
def test_범위_밖_문서는_검토를_차단하지_않는_명시_상태로_반환한다(mock_get_parser):
    parser = MagicMock()
    parser.parse.return_value = [_clause("선원은 선박에 승무하고 선박소유자의 지휘를 따른다.")]
    mock_get_parser.return_value = parser

    response = assess_contract_scope(file_path="/tmp/seafarer.pdf")

    assert response.status == "OUT_OF_SCOPE"
    assert response.suggested_contract_type is None
    assert "선원" in response.exclusion_markers


@patch("server.server.get_parser")
def test_애매한_유형은_경고하고_사용자_지정_review를_안내한다(mock_get_parser):
    parser = MagicMock()
    parser.parse.return_value = [_clause("소프트웨어 업무 범위와 보수 지급 방법을 정한다.")]
    mock_get_parser.return_value = parser

    response = assess_contract_scope(file_path="/tmp/near-domain.pdf")

    assert response.status == "CONTRACT_TYPE_UNCERTAIN"
    assert response.suggested_contract_type in {item.value for item in ContractType}
    assert "review_contract" in response.message


@patch("server.server.get_parser")
def test_충분한_sw_유형_근거는_추천_유형을_반환한다(mock_get_parser):
    parser = MagicMock()
    parser.parse.return_value = [
        _clause("프리랜서는 소프트웨어 개발 용역을 수행한다."),
        _clause("용역 대금과 저작권 귀속을 정한다."),
    ]
    mock_get_parser.return_value = parser

    response = assess_contract_scope(file_path="/tmp/sw.pdf")

    assert response.status == "IN_SCOPE"
    assert response.suggested_contract_type == ContractType.SW_FREELANCE.value
