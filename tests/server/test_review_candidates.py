"""법령 조회와 분리된 전체 계약 검토 도구의 공개 계약 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from contracts.enums import Category, ContractType, Deviation, ToxicPattern
from contracts.models import DeviationResult, StandardClause
from server.mapper import to_review_contract_candidates_response
from server.server import review_contract_candidates


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _standard(clause_id: str, category: Category = Category.PAYMENT) -> StandardClause:
    return StandardClause(
        clause_id=clause_id,
        contract_type=ContractType.SW_FREELANCE,
        category=category,
        title="대금 지급",
        text="표준조항 본문",
        source="표준계약서 / 제1조",
        version="2020",
    )


def test_mapper_separates_user_clause_results_and_missing_standards():
    """MISSING은 빈 user_clause와 무의미한 점수 대신 별도 배열로 변환한다."""
    matched_standard = _standard("standard-1")
    missing_standard = _standard("standard-2", Category.CONFIDENTIALITY)
    response = to_review_contract_candidates_response(
        status="OK",
        contract_type=ContractType.SW_FREELANCE.value,
        results=[
            DeviationResult(
                user_clause="사용자 조항",
                matched_standard=matched_standard,
                deviation=Deviation.NONE,
                confidence=0.91,
                grounding=[],
                toxic_patterns=[ToxicPattern.PAYMENT_DELAY_UNFAIR],
            ),
            DeviationResult(
                user_clause="비교 후보 없는 조항",
                matched_standard=None,
                deviation=Deviation.NO_MATCH,
                confidence=0.0,
            ),
            DeviationResult(
                user_clause="",
                matched_standard=missing_standard,
                deviation=Deviation.MISSING,
                confidence=0.0,
                grounding=[],
            ),
        ],
    )

    assert len(response.clause_results) == 2
    assert response.clause_results[0].match.status == "CANDIDATE_SELECTED"
    assert response.clause_results[0].match.score == pytest.approx(0.91)
    assert response.clause_results[0].toxic_patterns == ["PAYMENT_DELAY_UNFAIR"]
    assert response.clause_results[1].match.status == "NO_CANDIDATE"
    assert [item.standard.clause_id for item in response.missing_standard_clauses] == ["standard-2"]

    payload = response.model_dump(mode="json")
    assert "grounding" not in str(payload)
    assert "related_risk_clauses" not in str(payload)


@pytest.mark.anyio
@patch("server.server.get_grounder")
@patch("server.server.get_parser")
@patch("server.server._load_standards")
@patch("server.server.review_contract_pipe")
async def test_review_contract_candidates_does_not_create_or_call_law_grounder(
    mock_pipe, mock_load_standards, mock_get_parser, mock_get_grounder
):
    """신규 검토 경로는 법령 Grounder를 생성하거나 호출하지 않는다."""
    standard = _standard("standard-1")
    parser = MagicMock()
    parser.parse.return_value = [MagicMock(text="사용자 조항")]
    mock_get_parser.return_value = parser
    mock_load_standards.return_value = [standard]
    mock_pipe.return_value = [
        DeviationResult(
            user_clause="사용자 조항",
            matched_standard=standard,
            deviation=Deviation.NONE,
            confidence=0.9,
        )
    ]

    response = await review_contract_candidates(
        contract_type=ContractType.SW_FREELANCE.value,
        file_path="/dummy/path.pdf",
    )

    assert response.status == "OK"
    assert len(response.clause_results) == 1
    mock_get_grounder.assert_not_called()
    injected_grounder = mock_pipe.call_args.kwargs["grounder"]
    assert injected_grounder.get_grounding(Category.PAYMENT, ContractType.SW_FREELANCE) == []
    assert injected_grounder.query_law("민법 제665조") == []
