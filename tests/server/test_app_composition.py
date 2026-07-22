"""MCP 조립 루트의 등록 계약 테스트."""

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from app import create_app
from server.korean_law_wrapper import KoreanLawWrapper


@pytest.mark.anyio
async def test_create_app_registers_workshield_and_law_tools_and_resources():
    app = create_app()

    tools = {tool.name: tool for tool in await app.list_tools()}
    tool_names = set(tools)
    assert {
        "parse_contract", "parse_contract_clauses", "match_clause", "get_grounding", "review_contract",
        "review_contract_candidates", "get_category_grounding",
        "classify_clause", "classify_clause_candidate", "list_contract_types", "list_categories",
        "list_toxic_patterns", "list_toxic_pattern_details", "assess_contract_scope",
        "search_law", "get_law_text", "get_annexes", "legal_research",
        "legal_analysis", "discover_tools", "execute_tool", "search_decisions",
        "get_decision_text",
    } <= tool_names

    templates = {resource.uriTemplate for resource in await app.list_resource_templates()}
    assert templates == {
        "standard://{contract_type}",
        "standard://{contract_type}/{clause_id}",
    }


@pytest.mark.anyio
async def test_fastmcp_exposes_review_axes_and_partial_review_boundaries():
    """실제 FastMCP 설명에 검토 축·빈 목록·부분 검토 경계가 노출된다."""
    tools = {tool.name: tool for tool in await create_app().list_tools()}

    review_description = tools["review_contract"].description or ""
    for phrase in (
        "두 독립 축",
        "deviation",
        "toxic_patterns",
        "toxic_patterns=[]",
        "grounding=[]",
        "results=[]",
        "위법·합법",
    ):
        assert phrase in review_description

    classify_description = tools["classify_clause"].description or ""
    for phrase in (
        "독소 패턴 검색을 수행하지 않습니다",
        "MISSING",
        "grounding",
        "review_contract",
    ):
        assert phrase in classify_description

    candidates = tools["review_contract_candidates"]
    candidates_description = candidates.description or ""
    for phrase in (
        "법령 조회를 수행하지 않습니다",
        "clause_results",
        "missing_standard_clauses",
        "표준 대비 검토 후보",
    ):
        assert phrase in candidates_description
    assert "grounding" not in candidates.outputSchema["properties"]

    parse_clauses = tools["parse_contract_clauses"]
    parse_description = parse_clauses.description or ""
    for phrase in (
        "공개 DTO",
        "도메인 Clause",
        "classify_clause_candidate",
    ):
        assert phrase in parse_description
    assert "Clause" not in parse_clauses.outputSchema.get("$defs", {})
    assert "PublicClause" in parse_clauses.outputSchema.get("$defs", {})

    classify_candidate = tools["classify_clause_candidate"]
    classify_candidate_description = classify_candidate.description or ""
    for phrase in (
        "법령 조회를 수행하지 않습니다",
        "grounding 필드가 없습니다",
        "get_category_grounding",
        "MISSING",
    ):
        assert phrase in classify_candidate_description
    assert "grounding" not in str(classify_candidate.outputSchema)

    category_grounding = tools["get_category_grounding"]
    category_description = category_grounding.description or ""
    for phrase in (
        "UNMAPPED_CATEGORY",
        "NO_RESULT",
        "UPSTREAM_ERROR",
        "TIMEOUT",
        "OK일 때만",
    ):
        assert phrase in category_description


@pytest.mark.anyio
async def test_fastmcp_exposes_law_proxy_usage_and_result_boundaries():
    """법률 프록시 9개가 선택 기준·인자·반환·법률 판단 경계를 노출한다."""
    tools = {tool.name: tool for tool in await create_app().list_tools()}
    expected_phrases = {
        "search_law": ("lawId", "mst", "get_law_text"),
        "get_law_text": ("mst 또는 law_id", "jo", "6자리"),
        "get_annexes": ("knd", "byl_seq", "annex_no"),
        "legal_research": ("full_research", "document_review", "단일 조회"),
        "legal_analysis": ("verify_citations", "cite_check", "applicable_law", "impact_map"),
        "discover_tools": ("80개 이상", "execute_tool"),
        "execute_tool": ("discover_tools", "tool_name", "params"),
        "search_decisions": ("18개 도메인", "precedent", "get_decision_text"),
        "get_decision_text": ("decision_id", "full", "search_decisions"),
    }

    for name, phrases in expected_phrases.items():
        description = tools[name].description or ""
        for phrase in (*phrases, "result", "위법·합법"):
            assert phrase in description, f"{name} 설명에 '{phrase}'가 없음"
        assert tools[name].outputSchema == {
            "properties": {"result": {"title": "Result", "type": "string"}},
            "required": ["result"],
            "title": f"{name}Output",
            "type": "object",
        }


def test_get_law_text_rejects_missing_law_identifier_before_proxy_call():
    """mst와 law_id가 모두 없으면 외부 MCP 호출 전에 명시적으로 실패한다."""
    client = MagicMock()
    wrapper = KoreanLawWrapper(FastMCP("test"), client=client)

    with pytest.raises(ValueError, match="mst 또는 law_id"):
        wrapper.get_law_text(jo="000100")

    client.get_law_text.assert_not_called()
