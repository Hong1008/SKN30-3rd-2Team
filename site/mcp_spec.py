"""등록된 MCP 표면을 site/ 문서용 JSON 명세로 생성한다."""

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


SITE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = SITE_DIR / "mcp-spec.json"
_REQUIRED_STATIC_ASSETS = ("index.html", "styles.css", "app.js", ".nojekyll")


def _serialize(item: Any) -> dict[str, Any]:
    """MCP SDK 모델을 JSON 파일에 저장 가능한 사전으로 변환한다."""
    return item.model_dump(mode="json", by_alias=True, exclude_none=True)


async def build_mcp_spec(app: FastMCP) -> dict[str, Any]:
    """FastMCP의 런타임 discovery 결과를 결정론적 문서 명세로 구성한다."""
    tools, resources, resource_templates, prompts = await asyncio.gather(
        app.list_tools(),
        app.list_resources(),
        app.list_resource_templates(),
        app.list_prompts(),
    )

    return {
        "format": "workshield-mcp-spec",
        "formatVersion": 1,
        "server": {"name": app.name},
        "tools": sorted((_serialize(tool) for tool in tools), key=lambda tool: tool["name"]),
        "resources": sorted((_serialize(resource) for resource in resources), key=lambda resource: resource["uri"]),
        "resourceTemplates": sorted(
            (_serialize(template) for template in resource_templates),
            key=lambda template: template["uriTemplate"],
        ),
        "prompts": sorted((_serialize(prompt) for prompt in prompts), key=lambda prompt: prompt["name"]),
    }


async def write_mcp_spec(output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    """현재 앱 등록 내용을 site/의 JSON 명세 파일로 저장한다."""
    from app import create_app

    spec = await build_mcp_spec(create_app())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_static_assets() -> None:
    """GitHub Pages에 올릴 정적 문서 자산이 모두 있는지 확인한다."""
    missing = [name for name in _REQUIRED_STATIC_ASSETS if not (SITE_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"정적 MCP 문서 자산이 없습니다: {', '.join(missing)}")


async def build_mcp_docs() -> None:
    """명세를 생성하고 GitHub Pages용 정적 자산을 검증한다."""
    await write_mcp_spec()
    validate_static_assets()


def main() -> None:
    """기본 site 경로에 MCP 문서 자산을 빌드한다."""
    asyncio.run(build_mcp_docs())


if __name__ == "__main__":
    main()
