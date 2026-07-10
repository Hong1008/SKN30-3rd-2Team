"""MCP 조립 루트의 등록 계약 테스트."""

import pytest

from app import create_app


@pytest.mark.anyio
async def test_create_app_registers_workshield_and_law_tools_and_resources():
    app = create_app()

    tool_names = {tool.name for tool in await app.list_tools()}
    assert {
        "parse_contract", "match_clause", "get_grounding", "review_contract",
        "classify_clause", "list_contract_types", "list_categories",
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
