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
        "get_mcp_capabilities",
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

    search_display = tools["search_law"].inputSchema["properties"]["display"]
    assert search_display["minimum"] == 1
    assert search_display["maximum"] == 100

    assert tools["legal_research"].inputSchema["properties"]["task"]["enum"] == [
        "full_research", "law_system", "action_basis", "dispute_prep",
        "amendment_track", "ordinance_compare", "procedure_detail",
    ]
    assert tools["legal_analysis"].inputSchema["properties"]["mode"]["enum"] == [
        "verify_citations", "cite_check", "applicable_law", "impact_map",
    ]
    assert len(tools["search_decisions"].inputSchema["properties"]["domain"]["enum"]) == 18
    assert len(tools["get_decision_text"].inputSchema["properties"]["domain"]["enum"]) == 18

    get_law_properties = tools["get_law_text"].inputSchema["properties"]
    assert get_law_properties["mst"]["anyOf"][0]["pattern"] == r"^\d{6}$"
    assert get_law_properties["jo"]["anyOf"][0]["pattern"].startswith("^(?:")
    assert get_law_properties["ef_yd"]["anyOf"][0]["pattern"] == r"^\d{8}$"


@pytest.mark.anyio
async def test_fastmcp_exposes_numeric_input_constraints():
    """도구 설명뿐 아니라 입력 JSON Schema에서도 수치 범위를 제한한다."""
    tools = {tool.name: tool for tool in await create_app().list_tools()}

    match_top_k = tools["match_clause"].inputSchema["properties"]["top_k"]
    assert match_top_k["minimum"] == 1
    assert match_top_k["maximum"] == 10

    for name in ("classify_clause", "classify_clause_candidate"):
        threshold = tools[name].inputSchema["properties"]["match_threshold"]
        assert threshold["minimum"] == 0.0
        assert threshold["maximum"] == 1.0


def test_get_law_text_rejects_missing_law_identifier_before_proxy_call():
    """mst와 law_id가 모두 없으면 외부 MCP 호출 전에 명시적으로 실패한다."""
    client = MagicMock()
    wrapper = KoreanLawWrapper(FastMCP("test"), client=client)

    with pytest.raises(ValueError, match="mst 또는 law_id"):
        wrapper.get_law_text(jo="000100")

    client.get_law_text.assert_not_called()


@pytest.mark.parametrize(
    ("method_name", "args", "message"),
    [
        ("search_law", ("민법", 0), "display"),
        ("search_law", ("민법", 101), "display"),
        ("get_law_text", (), "mst 또는 law_id"),
        ("get_law_text", ("123", None, "000100", None), "mst"),
        ("get_law_text", ("123456", None, "제1항", None), "jo"),
        ("get_law_text", ("123456", None, "000100", "20261301"), "ef_yd"),
        ("get_annexes", ("민법", "9"), "knd"),
        ("get_annexes", ("민법", None, "123"), "byl_seq"),
        ("get_annexes", ("민법", None, None, "별표A"), "annex_no"),
        ("legal_research", ("질문", "unknown"), "task"),
        ("legal_analysis", ("unknown", {}), "mode"),
        ("legal_analysis", ("verify_citations", {}), "text"),
        ("legal_analysis", ("cite_check", {"caseNumber": ""}), "caseNumber"),
        ("legal_analysis", ("applicable_law", {"lawName": "민법"}), "date"),
        ("legal_analysis", ("impact_map", {"lawName": "민법"}), "jo"),
        ("discover_tools", ("",), "intent"),
        ("execute_tool", ("", {}), "tool_name"),
        ("search_decisions", ("unknown", "검색어"), "domain"),
        ("get_decision_text", ("unknown", "123456"), "domain"),
    ],
)
def test_law_proxy_rejects_documented_invalid_inputs_before_call(method_name, args, message):
    """문서에 명시된 enum·형식·필수 입력을 외부 호출 전에 검증한다."""
    client = MagicMock()
    wrapper = KoreanLawWrapper(FastMCP("test"), client=client)

    with pytest.raises(ValueError, match=message):
        getattr(wrapper, method_name)(*args)

    getattr(client, method_name).assert_not_called()


def test_search_decisions_rejects_unknown_option_before_proxy_call():
    """임의 kwargs가 외부 도구로 확산되지 않도록 공개 options 키를 제한한다."""
    client = MagicMock()
    wrapper = KoreanLawWrapper(FastMCP("test"), client=client)

    with pytest.raises(ValueError, match="options"):
        wrapper.search_decisions("precedent", "손해배상", {"unexpected": True})

    client.search_decisions.assert_not_called()


def test_law_proxy_forwards_valid_documented_inputs():
    """검증 보강 뒤에도 기존 성공 호출과 result 문자열 계약을 유지한다."""
    client = MagicMock()
    client.get_law_text.return_value = "법령 본문"
    client.legal_analysis.return_value = "검증 결과"
    wrapper = KoreanLawWrapper(FastMCP("test"), client=client)

    assert wrapper.get_law_text("123456", jo="제38조의2", ef_yd="20260101") == "법령 본문"
    assert wrapper.legal_analysis("applicable_law", {"lawName": "민법", "date": "20260101"}) == "검증 결과"

    client.get_law_text.assert_called_once_with(
        mst="123456", law_id=None, jo="제38조의2", ef_yd="20260101"
    )
    client.legal_analysis.assert_called_once_with(
        "applicable_law", lawName="민법", date="20260101"
    )
