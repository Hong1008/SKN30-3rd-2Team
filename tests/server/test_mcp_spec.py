"""MCP 문서 명세 생성과 등록 표면의 동기화를 검증한다."""

import json
from pathlib import Path

import pytest

from app import create_app
from server.mcp_spec import DEFAULT_OUTPUT_PATH, build_mcp_spec, write_mcp_spec


@pytest.mark.anyio
async def test_mcp_spec_includes_registered_tools_and_resource_templates(tmp_path: Path):
    """exporter는 FastMCP discovery 결과와 리소스 설명을 빠짐없이 보존해야 한다."""
    output_path = tmp_path / "mcp-spec.json"

    await write_mcp_spec(output_path)

    spec = json.loads(output_path.read_text(encoding="utf-8"))
    assert spec["format"] == "workshield-mcp-spec"
    assert spec["server"] == {"name": "WorkShield"}
    assert {tool["name"] for tool in spec["tools"]} >= {
        "parse_contract",
        "review_contract",
        "search_law",
    }
    templates = {template["uriTemplate"]: template for template in spec["resourceTemplates"]}
    assert "표준조항의 식별자·제목·카테고리 목록" in templates["standard://{contract_type}"]["description"]
    assert "표준조항의 전체 내용" in templates["standard://{contract_type}/{clause_id}"]["description"]
    assert {template["mimeType"] for template in templates.values()} == {"application/json"}


@pytest.mark.anyio
async def test_checked_in_mcp_spec_matches_current_registration():
    """도구·리소스 등록이 바뀌면 생성 명세도 함께 갱신되어야 한다."""
    expected = await build_mcp_spec(create_app())
    actual = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert actual == expected
