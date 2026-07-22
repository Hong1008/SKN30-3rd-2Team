"""MCP capability 발견 도구의 공개 계약 테스트."""

import pytest

from app import create_app
from server.capabilities import get_mcp_capabilities


def test_capabilities_exposes_recommended_workflows_and_legacy_replacements():
    """신규 클라이언트가 권장 흐름과 호환 도구 대체 관계를 발견할 수 있다."""
    response = get_mcp_capabilities()

    workflows = {workflow.name: workflow.steps for workflow in response.workflows}
    assert workflows["FULL_CONTRACT_REVIEW"] == [
        "assess_contract_scope",
        "review_contract_candidates",
        "get_category_grounding",
    ]
    assert workflows["SELECTED_CLAUSE_REVIEW"] == [
        "parse_contract_clauses",
        "classify_clause_candidate",
    ]

    replacements = {
        item.legacy_tool: item.recommended_tool for item in response.legacy_replacements
    }
    assert replacements == {
        "parse_contract": "parse_contract_clauses",
        "review_contract": "review_contract_candidates",
        "classify_clause": "classify_clause_candidate",
        "get_grounding": "get_category_grounding",
    }
    assert "위법·합법" in response.product_boundary


@pytest.mark.anyio
async def test_capabilities_is_registered_with_independent_public_schema():
    """capability 안내가 실제 MCP에 독립된 공개 DTO로 등록된다."""
    tools = {tool.name: tool for tool in await create_app().list_tools()}

    tool = tools["get_mcp_capabilities"]
    assert tool.inputSchema["properties"] == {}
    assert set(tool.outputSchema["properties"]) == {
        "schema_version",
        "product_boundary",
        "workflows",
        "legacy_replacements",
        "legal_proxy_note",
    }
