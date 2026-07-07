"""summarize() 구조화 출력 스키마 (OpenAI SDK response_format 용)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

DeviationLabel = Literal["MISSING", "EXTRA", "NO_MATCH"]


class Finding(BaseModel):
    title: str = Field(description="detections 항목의 title 값 그대로")
    deviation: DeviationLabel
    reason: str = Field(description="근거 기반 사유. NO_MATCH면 '근거를 찾지 못해 판단하지 않음'으로 고정")
    source: Optional[str] = Field(
        default=None, description="standard_source 또는 grounding 법령 근거. 없으면 null (지어내지 말 것)"
    )


class StructuredSummary(BaseModel):
    summary: str = Field(description="계약서 전체에 대한 3~5문장 한국어 요약")
    findings: list[Finding] = Field(description="detections 중 MISSING/EXTRA/NO_MATCH 항목별 상세")
