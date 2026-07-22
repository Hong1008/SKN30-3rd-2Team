"""MCP 문서 명세 생성과 등록 표면의 동기화를 검증한다."""

import importlib.util
import json
from pathlib import Path

import pytest

from app import create_app


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "site" / "mcp_spec.py"
_MODULE_SPEC = importlib.util.spec_from_file_location("workshield_mcp_spec", _SCRIPT_PATH)
assert _MODULE_SPEC is not None and _MODULE_SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_MODULE_SPEC)
_MODULE_SPEC.loader.exec_module(_MODULE)

DEFAULT_OUTPUT_PATH = _MODULE.DEFAULT_OUTPUT_PATH
build_mcp_docs = _MODULE.build_mcp_docs
build_mcp_spec = _MODULE.build_mcp_spec
write_mcp_spec = _MODULE.write_mcp_spec


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
        "review_contract_candidates",
        "get_category_grounding",
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


@pytest.mark.anyio
async def test_mcp_docs_build_has_static_ui_and_current_spec():
    """문서 빌드는 Pages에 필요한 정적 자산과 최신 명세를 함께 제공해야 한다."""
    await build_mcp_docs()

    site_dir = DEFAULT_OUTPUT_PATH.parent
    assert {"index.html", "styles.css", "app.js", ".nojekyll", "mcp-spec.json"} <= {
        path.name for path in site_dir.iterdir()
    }
    assert "mcp-spec.json" in (site_dir / "app.js").read_text(encoding="utf-8")
    assert "inputSchema" in (site_dir / "app.js").read_text(encoding="utf-8")
    assert "outputSchema" in (site_dir / "app.js").read_text(encoding="utf-8")
