"""법령 필드가 없는 단일 조항 검토 후보 도구의 공개 계약 테스트."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from contracts.enums import Category, ContractType
from contracts.models import StandardClause
from server.public_dto import ClassifyClauseCandidateResponse, PublicStandardClause
from server.server import classify_clause, classify_clause_candidate, match_clause


def _standard() -> StandardClause:
    return StandardClause(
        clause_id="sw-freelance-payment",
        contract_type=ContractType.SW_FREELANCE,
        category=Category.PAYMENT,
        title="보수 지급",
        text="표준조항 본문",
        source="표준계약서 / 제1조",
        version="2020",
    )


def _public_standard() -> PublicStandardClause:
    standard = _standard()
    return PublicStandardClause(
        clause_id=standard.clause_id,
        contract_type=standard.contract_type.value,
        category=standard.category.value,
        title=standard.title,
        text=standard.text,
        source=standard.source,
        version=standard.version,
    )


def test_OK_응답에는_deviation이_필요하다():
    with pytest.raises(ValidationError, match="OK 상태에는 deviation"):
        ClassifyClauseCandidateResponse(
            status="OK",
            contract_type="SW_FREELANCE",
        )


def test_CORPUS_UNAVAILABLE에는_부분_판정이_포함될_수_없다():
    with pytest.raises(ValidationError, match="실패 상태에는"):
        ClassifyClauseCandidateResponse(
            status="CORPUS_UNAVAILABLE",
            contract_type="SW_FREELANCE",
            deviation="NONE",
            confidence=0.9,
            matched_standard=_public_standard(),
        )


def test_신규_도구는_기존_판정과_같지만_grounding을_노출하지_않는다():
    standard = _standard()
    raw_hits = [{"id": standard.clause_id, "text": standard.text}]
    reranked = [{**raw_hits[0], "rerank_score": 0.91}]

    with (
        patch("server.server._load_standards", return_value=[standard]),
        patch("server.server.embedder.embed_query", return_value=[0.1]),
        patch("server.server.vector.hybrid_search", return_value=raw_hits),
        patch("server.server.reranker.rerank", return_value=reranked),
        patch("server.server.get_grounder") as get_grounder,
    ):
        legacy = classify_clause("보수 지급 조항", "SW_FREELANCE")
        response = classify_clause_candidate("보수 지급 조항", "SW_FREELANCE")

    assert response.status == legacy.status == "OK"
    assert response.deviation == legacy.deviation == "NONE"
    assert response.confidence == pytest.approx(legacy.confidence)
    assert response.matched_standard is not None
    assert response.matched_standard.clause_id == standard.clause_id
    assert "grounding" not in response.model_dump(mode="json")
    get_grounder.assert_not_called()


def test_검색_후보가_없으면_명시적_NO_MATCH를_반환한다():
    with (
        patch("server.server._load_standards", return_value=[_standard()]),
        patch("server.server.embedder.embed_query", return_value=[0.1]),
        patch("server.server.vector.hybrid_search", return_value=[]),
    ):
        response = classify_clause_candidate("대응 없는 조항", "SW_FREELANCE")

    assert response.status == "OK"
    assert response.deviation == "NO_MATCH"
    assert response.confidence == 0.0
    assert response.matched_standard is None


def test_코퍼스가_없으면_실패_상태만_반환한다():
    with patch("server.server._load_standards", return_value=[]):
        response = classify_clause_candidate("조항", "SW_FREELANCE")

    assert response.status == "CORPUS_UNAVAILABLE"
    assert response.deviation is None
    assert response.confidence == 0.0
    assert response.matched_standard is None


@pytest.mark.parametrize("top_k", [0, -1, 11])
def test_match_clause는_top_k_허용_범위를_벗어나면_검색_전에_거부한다(top_k):
    with (
        patch("server.server.embedder.embed_query") as embed_query,
        pytest.raises(ValueError, match="1 이상 10 이하"),
    ):
        match_clause("조항", "SW_FREELANCE", top_k=top_k)

    embed_query.assert_not_called()


@pytest.mark.parametrize("tool", [classify_clause, classify_clause_candidate])
@pytest.mark.parametrize("match_threshold", [-0.1, 1.1])
def test_단일_조항_분류는_임계값_허용_범위를_벗어나면_검색_전에_거부한다(
    tool, match_threshold
):
    with (
        patch("server.server._load_standards") as load_standards,
        pytest.raises(ValueError, match="0 이상 1 이하"),
    ):
        tool("조항", "SW_FREELANCE", match_threshold=match_threshold)

    load_standards.assert_not_called()


def test_벡터_hit가_DB_표준조항과_결합되지_않으면_EXTRA로_숨기지_않는다():
    raw_hits = [{"id": "stale-index-id", "text": "삭제된 표준조항"}]

    with (
        patch("server.server._load_standards", return_value=[_standard()]),
        patch("server.server.embedder.embed_query", return_value=[0.1]),
        patch("server.server.vector.hybrid_search", return_value=raw_hits),
        patch("server.server.reranker.rerank", return_value=raw_hits),
    ):
        response = classify_clause_candidate("조항", "SW_FREELANCE")

    assert response.status == "CORPUS_UNAVAILABLE"
    assert response.deviation is None
    assert response.confidence == 0.0
    assert response.matched_standard is None
    assert response.message is not None
    assert "인덱스" in response.message
