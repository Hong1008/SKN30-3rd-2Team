"""동결 도메인 모델을 직접 노출하는 기존 MCP 호환 응답 계약.

신규 도구는 이 모듈을 사용하지 않는다. 기존 도구의 출력 스키마를 깨지 않고 유지하기
위해 도메인 결합 DTO만 명시적으로 격리한다.
"""

from typing import Literal

from pydantic import BaseModel, Field

from contracts.models import Clause, DeviationResult, GroundingLaw, StandardClause


class ParseContractResponse(BaseModel):
    """계약서 파싱 결과를 도메인 Clause로 반환하는 기존 호환 응답."""

    status: Literal["OK", "EMPTY_DOCUMENT"] = Field(
        ...,
        description="처리 상태. OK는 조항을 추출했음을, EMPTY_DOCUMENT는 추출 가능한 조항이 없음을 뜻한다.",
    )
    contract_type: str | None = Field(
        default=None,
        description="호출자가 제공한 계약 유형. 제공하지 않았거나 EMPTY_DOCUMENT인 경우에도 None일 수 있다.",
    )
    clauses: list[Clause] = Field(
        ...,
        description="문서에서 순서대로 추출한 조항 목록. status가 EMPTY_DOCUMENT이면 빈 목록이다.",
    )
    message: str | None = Field(default=None, description="상태의 원인이나 다음 조치를 설명하는 보조 메시지.")


class GetGroundingResponse(BaseModel):
    """조항 또는 카테고리에 대한 기존 참고 법령 조회 결과."""

    status: Literal["OK", "NO_RESULT", "INVALID_INPUT"] = Field(
        ...,
        description="처리 상태. NO_RESULT는 관련 조문을 찾지 못했음을, INVALID_INPUT은 조회 조건이 없었음을 뜻한다.",
    )
    grounding: list[GroundingLaw] = Field(
        ...,
        description="관련 법령 조문 목록. 참고 자료이며 위법·합법 등 법률적 결론을 의미하지 않는다.",
    )
    message: str | None = Field(default=None, description="빈 결과 또는 잘못된 입력의 이유를 설명하는 보조 메시지.")


class ReviewContractResponse(BaseModel):
    """도메인 DeviationResult를 반환하는 기존 전체 검토 응답."""

    status: Literal[
        "OK", "EMPTY_DOCUMENT", "CORPUS_UNAVAILABLE", "INVALID_CONFIG", "PIPELINE_ERROR"
    ] = Field(
        ...,
        description="처리 상태. OK가 아닌 경우 results는 빈 목록일 수 있으므로 반드시 상태를 먼저 확인한다.",
    )
    contract_type: str = Field(..., description="전체 검토의 비교 기준으로 사용한 표준계약서 유형.")
    results: list[DeviationResult] = Field(
        ...,
        description="조항별 표준 대비 검토 후보 목록. 빈 목록은 문제 없음이 아니라 status와 함께 해석해야 한다.",
    )
    message: str | None = Field(default=None, description="처리 상태, 실패 원인 또는 다음 조치를 설명하는 보조 메시지.")


class ClassifyClauseResponse(BaseModel):
    """도메인 표준조항과 법령 필드를 반환하는 기존 단일 조항 응답."""

    status: Literal["OK", "CORPUS_UNAVAILABLE"] = Field(
        ...,
        description="처리 상태. CORPUS_UNAVAILABLE이면 해당 계약 유형의 표준 코퍼스를 사용할 수 없다.",
    )
    contract_type: str = Field(..., description="비교 기준으로 사용한 표준계약서 유형.")
    deviation: str | None = Field(
        default=None,
        description="표준 대비 검토 후보 표식(NO_MATCH, EXTRA, NONE). MISSING은 전체 계약서 비교가 필요하므로 review_contract에서만 반환된다.",
    )
    confidence: float = Field(
        default=0.0,
        description="선택된 표준조항과의 정규화 매칭 점수(0.0~1.0). 법률적 결론이나 계약상 유불리를 뜻하지 않는다.",
    )
    matched_standard: StandardClause | None = Field(
        default=None,
        description="선택된 대응 표준조항. 대응 후보가 없으면 None이다.",
    )
    grounding: list[GroundingLaw] = Field(
        default_factory=list,
        description="관련 법령 조문 목록. 이 도구는 법령 조회를 수행하지 않으므로 현재 항상 빈 목록이며, 관련 법령이 없다는 뜻은 아니다.",
    )
    message: str | None = Field(default=None, description="코퍼스를 사용할 수 없는 이유 등을 설명하는 보조 메시지.")
