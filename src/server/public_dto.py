"""내부 도메인 모델과 분리된 신규 MCP 공개 응답 계약."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _PublicModel(BaseModel):
    """알 수 없는 필드를 허용하지 않는 공개 DTO 공통 설정."""

    model_config = ConfigDict(extra="forbid")


class PublicClause(_PublicModel):
    """파싱된 사용자 계약서 조항의 공개 표현."""

    idx: int = Field(..., ge=1, description="문서에서의 1부터 시작하는 조항 순서.")
    num: str = Field(..., description="원문에 표시된 조항 번호.")
    title: str = Field(..., description="조항 제목. 원문에 제목이 없으면 빈 문자열일 수 있다.")
    text: str = Field(..., min_length=1, description="조항의 전체 본문.")


class ParseContractClausesResponse(_PublicModel):
    """도메인 모델과 분리된 계약서 조항 파싱 결과."""

    status: Literal["OK", "EMPTY_DOCUMENT"] = Field(
        ...,
        description="처리 상태. OK이면 clauses가 최소 1건이고 EMPTY_DOCUMENT이면 빈 목록이다.",
    )
    contract_type: str | None = Field(
        default=None,
        description="호출자가 제공한 계약 유형. 제공하지 않았다면 null이다.",
    )
    clauses: list[PublicClause] = Field(
        default_factory=list,
        description="문서 순서대로 복사한 공개 조항 목록.",
    )
    message: str | None = Field(default=None, description="빈 문서 상태의 원인과 다음 조치.")

    @model_validator(mode="after")
    def validate_status_and_clauses(self) -> "ParseContractClausesResponse":
        """파싱 상태와 조항 배열의 관계를 강제한다."""
        if self.status == "OK" and not self.clauses:
            raise ValueError("OK 상태에는 최소 한 건의 clauses가 필요합니다.")
        if self.status == "EMPTY_DOCUMENT" and self.clauses:
            raise ValueError("EMPTY_DOCUMENT에는 clauses를 포함할 수 없습니다.")
        return self


class MatchCandidate(_PublicModel):
    """단일 조항 검색에서 반환하는 표준조항 후보."""

    clause_id: str = Field(..., description="후보 표준조항의 고유 식별자.")
    score: float = Field(
        ...,
        description="검색 융합 점수. 판정 임계값과 스케일이 다르므로 법률적 결론으로 해석하지 않는다.",
    )
    standard_text: str = Field(..., description="후보 표준조항의 본문.")
    title: str = Field(..., description="후보 표준조항의 제목.")
    category: str = Field(..., description="후보 표준조항의 카테고리 값.")
    source: str = Field(..., description="후보 표준조항의 출처 정보.")


class MatchClauseResponse(_PublicModel):
    """단일 조항의 표준조항 후보 검색 결과."""

    status: Literal["OK", "NO_RESULT"] = Field(
        ...,
        description="처리 상태. NO_RESULT는 검색 후보가 없음을 뜻하며 적법성이나 안전성을 뜻하지 않는다.",
    )
    contract_type: str = Field(..., description="후보 검색에 사용한 표준계약서 유형.")
    candidates: list[MatchCandidate] = Field(
        ...,
        description="점수 순으로 정렬된 표준조항 검색 후보. NO_RESULT이면 빈 목록이다.",
    )
    message: str | None = Field(default=None, description="빈 검색 결과의 이유를 설명하는 메시지.")


class ListContractTypesResponse(_PublicModel):
    """지원하는 표준계약서 유형 목록."""

    contract_types: list[str] = Field(..., description="도구 입력에 사용할 수 있는 현재 지원 계약 유형 값.")


class CategoryInfo(_PublicModel):
    """조항 분류 카테고리의 공개 메타데이터."""

    value: str = Field(..., description="도구 입력과 결과에 사용하는 카테고리 식별 값.")
    description: str = Field(..., description="카테고리가 나타내는 계약 조항 주제.")
    anchors: list[str] = Field(..., description="카테고리 판별에 사용하는 대표 키워드 또는 문구.")


class ListCategoriesResponse(_PublicModel):
    """지원 카테고리와 메타데이터 목록."""

    categories: list[CategoryInfo] = Field(..., description="계약 유형 조건으로 필터링된 카테고리 목록.")


class ListToxicPatternsResponse(_PublicModel):
    """탐지 대상 주의 문구 패턴 식별자 목록."""

    patterns: list[str] = Field(..., description="검토 결과에 나타날 수 있는 주의 문구 패턴 값.")


class ToxicPatternDetail(_PublicModel):
    """주의 문구 패턴의 공개 메타데이터."""

    pattern: str = Field(..., description="주의 문구 패턴 식별 값.")
    title: str = Field(..., description="사람이 읽는 패턴 대표 제목.")
    category: str | None = Field(default=None, description="패턴이 속하는 조항 카테고리.")
    example_count: int = Field(..., ge=0, description="연결된 큐레이션 예시 수. 위험도 점수가 아니다.")


class ListToxicPatternDetailsResponse(_PublicModel):
    """주의 문구 패턴의 상세 메타데이터 목록."""

    patterns: list[ToxicPatternDetail] = Field(..., description="패턴별 대표 제목·카테고리·예시 수.")


class ContractTypeScopeScore(_PublicModel):
    """계약 유형별 결정론적 범위 근거 점수."""

    contract_type: str = Field(..., description="근거 점수를 계산한 지원 계약 유형.")
    score: int = Field(..., description="결정론적 근거 점수. 법률 판단이나 확률이 아니다.")


class AssessContractScopeResponse(_PublicModel):
    """지원 표준 코퍼스 범위 판별 결과."""

    status: Literal[
        "IN_SCOPE", "CONTRACT_TYPE_UNCERTAIN", "OUT_OF_SCOPE", "EMPTY_DOCUMENT"
    ] = Field(..., description="범위 판별 상태. 불확실 상태는 검토 차단이 아닌 경고다.")
    suggested_contract_type: str | None = Field(
        default=None,
        description="근거가 충분할 때 제안하는 계약 유형. 최종 선택은 사용자에게 있다.",
    )
    candidates: list[ContractTypeScopeScore] = Field(
        default_factory=list,
        description="계약 유형별 범위 근거 점수 목록.",
    )
    matched_clause_count: int = Field(
        default=0,
        ge=0,
        description="지원 범위 앵커에 대응된 입력 조항 수.",
    )
    exclusion_markers: list[str] = Field(
        default_factory=list,
        description="지원 범위 밖 문서를 시사하는 탐지 표식.",
    )
    message: str | None = Field(default=None, description="범위 상태 해석과 권장 다음 단계.")


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


class ClassifyClauseCandidateResponse(_PublicModel):
    """법령 필드가 없는 단일 조항의 표준 대비 검토 후보 결과."""

    status: Literal["OK", "CORPUS_UNAVAILABLE"] = Field(
        ...,
        description="도구 실행 상태. CORPUS_UNAVAILABLE이면 판정 필드는 비어 있다.",
    )
    contract_type: str = Field(..., description="비교 기준으로 사용한 표준계약서 유형.")
    deviation: Literal["NONE", "EXTRA", "NO_MATCH"] | None = Field(
        default=None,
        description="표준 대비 검토 후보 표식. MISSING은 계약서 전체 비교에서만 판단한다.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="선택된 표준조항의 정규화 재정렬 점수. 법률적 결론을 의미하지 않는다.",
    )
    matched_standard: PublicStandardClause | None = Field(
        default=None,
        description="선택된 대응 표준조항. 대응 후보가 없으면 null이다.",
    )
    message: str | None = Field(default=None, description="실패 원인 또는 다음 조치를 설명하는 메시지.")

    @model_validator(mode="after")
    def validate_status_and_classification(self) -> "ClassifyClauseCandidateResponse":
        """실행 상태와 단일 조항 판정 결과의 모순을 차단한다."""
        if self.status != "OK":
            if self.deviation is not None or self.confidence != 0.0 or self.matched_standard is not None:
                raise ValueError("실패 상태에는 부분 판정 결과를 포함할 수 없습니다.")
            return self

        if self.deviation is None:
            raise ValueError("OK 상태에는 deviation이 필요합니다.")
        if self.deviation == "NONE" and self.matched_standard is None:
            raise ValueError("NONE에는 선택된 표준조항이 필요합니다.")
        if self.deviation == "NO_MATCH" and (
            self.matched_standard is not None or self.confidence != 0.0
        ):
            raise ValueError("NO_MATCH에는 표준조항이나 매칭 점수를 포함할 수 없습니다.")
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
