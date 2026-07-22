"""내부 도메인 모델과 분리된 신규 MCP 공개 응답 계약."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _PublicModel(BaseModel):
    """알 수 없는 필드를 허용하지 않는 공개 DTO 공통 설정."""

    model_config = ConfigDict(extra="forbid")


class PublicStandardClause(_PublicModel):
    """클라이언트에 노출하는 표준조항 원문과 출처."""

    clause_id: str = Field(..., description="표준조항의 고유 식별자.")
    contract_type: str = Field(..., description="표준조항이 속한 계약 유형.")
    category: str = Field(..., description="후속 카테고리 기반 법령 조회에 사용할 분류 값.")
    title: str = Field(..., description="표준조항 제목.")
    text: str = Field(..., description="표준조항 전체 본문.")
    source: str = Field(..., description="표준조항의 원문 출처.")
    version: str = Field(..., description="표준계약서의 배포 또는 개정 버전.")


class CandidateSelected(_PublicModel):
    """재정렬 결과에서 비교할 표준조항 후보를 선택한 상태."""

    status: Literal["CANDIDATE_SELECTED"] = Field(
        ..., description="비교할 표준조항 후보와 정규화 점수가 있음을 뜻한다."
    )
    standard: PublicStandardClause = Field(..., description="선택된 비교용 표준조항 후보.")
    score: float = Field(
        ..., ge=0.0, le=1.0,
        description="선택된 표준조항 후보의 정규화 재정렬 점수(0.0~1.0).",
    )


class NoCandidate(_PublicModel):
    """비교할 표준조항 후보를 선택하지 못한 상태."""

    status: Literal["NO_CANDIDATE"] = Field(
        ..., description="검색·재정렬 후 선택할 표준조항 후보가 없음을 뜻한다."
    )


StandardMatch = Annotated[
    Union[CandidateSelected, NoCandidate],
    Field(discriminator="status"),
]


class ClauseReviewCandidate(_PublicModel):
    """계약서에 실제로 존재하는 사용자 조항의 표준 대비 검토 후보."""

    user_clause: str = Field(..., min_length=1, description="분석한 사용자 계약서 조항 원문.")
    deviation: Literal["NONE", "EXTRA", "NO_MATCH"] = Field(
        ...,
        description="사용자 조항에서 표준조항 방향으로 계산한 검토 후보 표식. MISSING은 이 배열에 포함하지 않는다.",
    )
    match: StandardMatch = Field(..., description="비교용 표준조항 후보 선택 여부와, 선택된 경우 그 근거.")
    toxic_patterns: list[str] = Field(
        default_factory=list,
        description="알려진 주의 문구와의 유사 신호. 빈 목록은 안전·합법 판정이 아니다.",
    )

    @model_validator(mode="after")
    def validate_deviation_and_match(self) -> "ClauseReviewCandidate":
        """명시 상태와 후보 선택 여부의 모순을 차단한다."""
        if self.deviation == "NONE" and self.match.status != "CANDIDATE_SELECTED":
            raise ValueError("NONE은 선택된 표준조항 후보가 필요합니다.")
        if self.deviation == "NO_MATCH" and self.match.status != "NO_CANDIDATE":
            raise ValueError("NO_MATCH에는 표준조항 후보가 없어야 합니다.")
        return self


class MissingStandardCandidate(_PublicModel):
    """계약서 전체에서 대응 조항을 찾지 못한 표준조항 후보."""

    standard: PublicStandardClause = Field(
        ..., description="사용자 계약서 전체에서 대응되지 않은 표준조항. 누락의 법률적 의미를 확정하지 않는다."
    )


class ReviewContractCandidatesResponse(_PublicModel):
    """법령 조회와 분리된 계약서 전체의 표준 대비 검토 후보 결과."""

    status: Literal[
        "OK", "EMPTY_DOCUMENT", "CORPUS_UNAVAILABLE", "INVALID_CONFIG", "PIPELINE_ERROR"
    ] = Field(..., description="도구 실행 상태. OK가 아니면 두 결과 배열은 비어 있다.")
    contract_type: str = Field(..., description="비교 기준으로 사용한 표준계약서 유형.")
    clause_results: list[ClauseReviewCandidate] = Field(
        default_factory=list,
        description="계약서에 실제로 존재하는 사용자 조항의 검토 후보. 입력 조항 순서를 유지한다.",
    )
    missing_standard_clauses: list[MissingStandardCandidate] = Field(
        default_factory=list,
        description="계약서 전체에서 대응되지 않은 표준조항 후보. user_clause나 매칭 점수를 사용하지 않는다.",
    )
    message: str | None = Field(default=None, description="처리 실패 원인 또는 다음 조치를 설명하는 메시지.")

    @model_validator(mode="after")
    def validate_failed_response_is_empty(self) -> "ReviewContractCandidatesResponse":
        """실패 상태에 부분 결과가 섞이는 것을 차단한다."""
        if self.status != "OK" and (self.clause_results or self.missing_standard_clauses):
            raise ValueError("OK가 아닌 응답에는 검토 결과를 포함할 수 없습니다.")
        return self


class PublicGroundingLaw(_PublicModel):
    """카테고리 조회로 얻은 법령 조문 공개 모델."""

    법령명: str = Field(..., description="법제처 공식 법령명.")
    조번호: str = Field(..., description="법령 내 조문 번호.")
    본문: str = Field(..., description="조회된 법령 조문 본문.")
    출처: str = Field(..., description="조문 원문의 출처 좌표 또는 제공 기관.")


class GetCategoryGroundingResponse(_PublicModel):
    """카테고리 정적 매핑과 외부 검색 결과를 구분하는 법령 조회 응답."""

    status: Literal[
        "OK", "NO_RESULT", "UNMAPPED_CATEGORY", "UPSTREAM_ERROR", "TIMEOUT"
    ] = Field(
        ...,
        description=(
            "법령 조회 상태. UNMAPPED_CATEGORY는 정적 매핑 없음, NO_RESULT는 "
            "매핑된 질의를 실행했지만 결과 없음이다."
        ),
    )
    category: str = Field(..., description="조회 기준으로 사용한 조항 카테고리.")
    contract_type: str | None = Field(
        default=None,
        description="카테고리 매핑 선택에 사용한 계약 유형. 생략했다면 null.",
    )
    grounding: list[PublicGroundingLaw] = Field(
        default_factory=list,
        description="조회된 법령 조문. OK일 때만 최소 1건이며 나머지 상태에서는 빈 목록이다.",
    )
    message: str | None = Field(default=None, description="상태의 원인과 가능한 다음 조치.")

    @model_validator(mode="after")
    def validate_status_and_grounding(self) -> "GetCategoryGroundingResponse":
        """상태와 법령 배열이 서로 모순되지 않도록 강제한다."""
        if self.status == "OK" and not self.grounding:
            raise ValueError("OK 상태에는 최소 한 건의 grounding이 필요합니다.")
        if self.status != "OK" and self.grounding:
            raise ValueError("OK가 아닌 상태에는 grounding을 포함할 수 없습니다.")
        return self
