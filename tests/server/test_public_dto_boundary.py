"""MCP 공개 DTO와 동결 도메인 모델의 경계 테스트."""

from typing import get_type_hints
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from contracts.models import Clause
from server.public_dto import ParseContractClausesResponse
from server.server import (
    assess_contract_scope,
    classify_clause_candidate,
    get_category_grounding,
    match_clause,
    parse_contract_clauses,
    review_contract_candidates,
)


def test_권장_MCP_도구의_반환형은_public_dto에_속한다():
    """신규 권장 경로는 server.dto나 contracts 모델을 반환형으로 사용하지 않는다."""
    tools = (
        assess_contract_scope,
        match_clause,
        parse_contract_clauses,
        review_contract_candidates,
        classify_clause_candidate,
        get_category_grounding,
    )

    for tool in tools:
        return_type = get_type_hints(tool)["return"]
        assert return_type.__module__ == "server.public_dto", tool.__name__


def test_공개_파싱_DTO는_도메인_Clause를_JSON_스키마에_노출하지_않는다():
    schema = ParseContractClausesResponse.model_json_schema()

    assert "Clause" not in schema.get("$defs", {})
    assert "PublicClause" in schema.get("$defs", {})
    assert set(schema["properties"]) == {
        "status",
        "contract_type",
        "clauses",
        "message",
    }


def test_OK_파싱_응답은_최소_한_조항이_필요하다():
    with pytest.raises(ValidationError, match="OK 상태에는"):
        ParseContractClausesResponse(status="OK", clauses=[])


def test_EMPTY_DOCUMENT에는_조항을_포함할_수_없다():
    with pytest.raises(ValidationError, match="EMPTY_DOCUMENT"):
        ParseContractClausesResponse(
            status="EMPTY_DOCUMENT",
            clauses=[{"idx": 1, "num": "제1조", "title": "목적", "text": "본문"}],
        )


def test_parse_contract_clauses는_한번만_파싱하고_공개_DTO로_복사한다():
    parser = MagicMock()
    parser.parse.return_value = [Clause(idx=1, num="제1조", title="목적", text="본문")]

    with patch("server.server.get_parser", return_value=parser):
        response = parse_contract_clauses(
            file_path="/dummy/contract.pdf",
            contract_type="SW_FREELANCE",
        )

    assert response.status == "OK"
    assert response.contract_type == "SW_FREELANCE"
    assert response.clauses[0].model_dump() == {
        "idx": 1,
        "num": "제1조",
        "title": "목적",
        "text": "본문",
    }
    parser.parse.assert_called_once_with("/dummy/contract.pdf")
