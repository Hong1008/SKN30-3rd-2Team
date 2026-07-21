"""등록된 MCP 표면을 문서용 JSON 명세로 내보낸다."""

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "docs" / "mcp-spec.json"


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
    """현재 앱 등록 내용을 JSON 명세 파일로 저장한다."""
    from app import create_app

    spec = await build_mcp_spec(create_app())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """기본 문서 경로에 MCP 명세를 생성한다."""
    asyncio.run(write_mcp_spec())


if __name__ == "__main__":
    main()
