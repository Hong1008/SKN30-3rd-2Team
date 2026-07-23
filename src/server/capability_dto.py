"""WorkShield MCP 사용 경로를 설명하는 공개 DTO."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _CapabilityModel(BaseModel):
    """알 수 없는 필드를 허용하지 않는 capability DTO 공통 설정."""

    model_config = ConfigDict(extra="forbid")


class ToolWorkflow(_CapabilityModel):
    """클라이언트가 따를 수 있는 권장 도구 호출 흐름."""

    name: str = Field(..., min_length=1, description="워크플로우 식별 이름.")
    description: str = Field(..., min_length=1, description="워크플로우의 사용 목적과 경계.")
    steps: list[str] = Field(..., min_length=1, description="권장 호출 순서의 도구 이름.")


class LegacyToolReplacement(_CapabilityModel):
    """기존 호환 도구와 신규 권장 도구의 대응 관계."""

    legacy_tool: str = Field(..., min_length=1, description="기존 응답 계약을 유지하는 호환 도구.")
    recommended_tool: str = Field(..., min_length=1, description="신규 클라이언트가 사용할 권장 도구.")
    reason: str = Field(..., min_length=1, description="신규 도구를 권장하는 계약상 이유.")


class GetMcpCapabilitiesResponse(_CapabilityModel):
    """WorkShield가 권장하는 MCP 도구 조합과 호환 경로."""

    schema_version: Literal["1.0"] = Field(..., description="이 capability 응답 자체의 스키마 버전.")
    product_boundary: str = Field(..., description="1차 MCP 결과의 해석 범위.")
    workflows: list[ToolWorkflow] = Field(..., min_length=1, description="용도별 권장 도구 호출 흐름.")
    legacy_replacements: list[LegacyToolReplacement] = Field(
        ..., description="호환 도구에서 신규 권장 도구로의 대응표."
    )
    legal_proxy_note: str = Field(..., description="외부 법령·판례 프록시 결과의 사용상 주의점.")
