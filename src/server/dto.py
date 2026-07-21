from typing import Literal, Optional
from pydantic import BaseModel, Field
from contracts.models import Clause, GroundingLaw, DeviationResult, StandardClause


class ParseContractResponse(BaseModel):
    """계약서 파싱 결과."""

    status: Literal["OK", "EMPTY_DOCUMENT"] = Field(
        ..., description="처리 상태. OK는 조항을 추출했음을, EMPTY_DOCUMENT는 추출 가능한 조항이 없음을 뜻한다."
    )
    contract_type: Optional[str] = Field(
        default=None,
        description="호출자가 제공한 계약 유형. 제공하지 않았거나 EMPTY_DOCUMENT인 경우에도 None일 수 있다.",
    )
    clauses: list[Clause] = Field(
        ..., description="문서에서 순서대로 추출한 조항 목록. status가 EMPTY_DOCUMENT이면 빈 목록이다."
    )
    message: Optional[str] = Field(default=None, description="상태의 원인이나 다음 조치를 설명하는 보조 메시지.")


class GetGroundingResponse(BaseModel):
    """조항 또는 카테고리에 대한 참고 법령 조회 결과."""

    status: Literal["OK", "NO_RESULT", "INVALID_INPUT"] = Field(
        ..., description="처리 상태. NO_RESULT는 관련 조문을 찾지 못했음을, INVALID_INPUT은 조회 조건이 없었음을 뜻한다."
    )
    grounding: list[GroundingLaw] = Field(
        ..., description="관련 법령 조문 목록. 참고 자료이며 위법·합법 등 법률적 결론을 의미하지 않는다."
    )
    message: Optional[str] = Field(default=None, description="빈 결과 또는 잘못된 입력의 이유를 설명하는 보조 메시지.")


class MatchCandidate(BaseModel):
    """단일 조항 검색에서 반환하는 표준조항 후보."""

    clause_id: str = Field(..., description="후보 표준조항의 고유 식별자.")
    score: float = Field(
        ..., description="검색 융합 점수. 판정 임계값과 스케일이 다르므로 매칭 성공·실패나 법률적 결론으로 해석하면 안 된다."
    )
    standard_text: str = Field(..., description="후보 표준조항의 본문.")
    title: str = Field(..., description="후보 표준조항의 제목.")
    category: str = Field(..., description="후보 표준조항의 분류 카테고리 값.")
    source: str = Field(..., description="후보 표준조항의 출처 정보.")


class MatchClauseResponse(BaseModel):
    """단일 조항의 표준조항 후보 검색 결과."""

    status: Literal["OK", "NO_RESULT"] = Field(
        ..., description="처리 상태. NO_RESULT는 검색 후보가 없음을 뜻하며, 조항의 적법성이나 안전성을 뜻하지 않는다."
    )
    contract_type: str = Field(..., description="후보 검색에 사용한 표준계약서 유형.")
    candidates: list[MatchCandidate] = Field(
        ..., description="점수 순으로 정렬된 표준조항 검색 후보. status가 NO_RESULT이면 빈 목록이다."
    )
    message: Optional[str] = Field(default=None, description="빈 검색 결과의 이유 등을 설명하는 보조 메시지.")


class ReviewContractResponse(BaseModel):
    """계약서 전체의 표준 대비 검토 후보 결과."""

    status: Literal["OK", "EMPTY_DOCUMENT", "CORPUS_UNAVAILABLE", "INVALID_CONFIG", "PIPELINE_ERROR"] = Field(
        ..., description="처리 상태. OK가 아닌 경우 results는 빈 목록일 수 있으므로 반드시 상태를 먼저 확인한다."
    )
    contract_type: str = Field(..., description="전체 검토의 비교 기준으로 사용한 표준계약서 유형.")
    results: list[DeviationResult] = Field(
        ..., description="조항별 표준 대비 검토 후보 목록. 빈 목록은 문제 없음이 아니라 status와 함께 해석해야 한다."
    )
    message: Optional[str] = Field(default=None, description="처리 상태, 실패 원인 또는 다음 조치를 설명하는 보조 메시지.")


class ClassifyClauseResponse(BaseModel):
    """단일 조항의 표준 대비 검토 후보 결과."""

    status: Literal["OK", "CORPUS_UNAVAILABLE"] = Field(
        ..., description="처리 상태. CORPUS_UNAVAILABLE이면 해당 계약 유형의 표준 코퍼스를 사용할 수 없다."
    )
    contract_type: str = Field(..., description="비교 기준으로 사용한 표준계약서 유형.")
    deviation: Optional[str] = Field(
        default=None,
        description="표준 대비 검토 후보 표식(NO_MATCH, EXTRA, NONE). MISSING은 전체 계약서 비교가 필요하므로 review_contract에서만 반환된다.",
    )
    confidence: float = Field(
        default=0.0,
        description="선택된 표준조항과의 정규화 매칭 점수(0.0~1.0). 법률적 결론이나 계약상 유불리를 뜻하지 않는다.",
    )
    matched_standard: Optional[StandardClause] = Field(
        default=None, description="선택된 대응 표준조항. 대응 후보가 없으면 None이다."
    )
    grounding: list[GroundingLaw] = Field(
        default_factory=list,
        description="관련 법령 조문 목록. 이 도구는 법령 조회를 수행하지 않으므로 현재 항상 빈 목록이며, 관련 법령이 없다는 뜻은 아니다.",
    )
    message: Optional[str] = Field(default=None, description="코퍼스를 사용할 수 없는 이유 등을 설명하는 보조 메시지.")


class ListContractTypesResponse(BaseModel):
    """지원하는 표준계약서 유형 목록."""

    contract_types: list[str] = Field(..., description="다른 도구의 contract_type 인자에 사용할 수 있는 현재 지원 계약 유형 값 목록.")


class CategoryInfo(BaseModel):
    """조항 분류 카테고리의 메타데이터."""

    value: str = Field(..., description="도구의 category 인자와 결과에 사용하는 카테고리 식별 값.")
    description: str = Field(..., description="카테고리가 나타내는 계약 조항 주제의 설명.")
    anchors: list[str] = Field(..., description="해당 카테고리 판별에 사용하는 대표 키워드 또는 문구 목록.")


class ListCategoriesResponse(BaseModel):
    """지원 카테고리와 메타데이터 목록."""

    categories: list[CategoryInfo] = Field(..., description="계약 유형 조건에 따라 필터링된 카테고리 메타데이터 목록.")


class ListToxicPatternsResponse(BaseModel):
    """탐지 대상 독소조항 패턴 식별자 목록."""

    patterns: list[str] = Field(..., description="review_contract 결과의 toxic_patterns에 나타날 수 있는 패턴 enum 값 목록.")


class ToxicPatternDetail(BaseModel):
    """독소조항 패턴을 사람이 읽을 수 있도록 보강한 메타데이터."""

    pattern: str = Field(..., description="독소조항 패턴 enum 값(예: IP_TOTAL_FREE).")
    title: str = Field(..., description="사람이 읽는 패턴 대표 제목.")
    category: Optional[str] = Field(default=None, description="패턴이 속하는 조항 카테고리. 지정되지 않은 패턴이면 None이다.")
    example_count: int = Field(..., description="해당 패턴에 연결된 큐레이션 예시 문구의 수. 발생 빈도나 위험도 점수가 아니다.")


class ListToxicPatternDetailsResponse(BaseModel):
    """독소조항 패턴의 상세 메타데이터 목록."""

    patterns: list[ToxicPatternDetail] = Field(..., description="패턴 enum 값별 대표 제목·카테고리·예시 수 목록.")


class ContractTypeScopeScore(BaseModel):
    """범위 판별에서 계약유형별로 계산된 결정론적 근거 점수."""

    contract_type: str = Field(..., description="범위 판별의 근거 점수를 계산한 지원 계약 유형.")
    score: int = Field(..., description="카테고리 앵커와 계약유형 표식으로 계산한 결정론적 근거 점수. 법률 판단이나 확률이 아니다.")


class AssessContractScopeResponse(BaseModel):
    """지원 표준 코퍼스 범위 판별 결과."""

    status: Literal["IN_SCOPE", "CONTRACT_TYPE_UNCERTAIN", "OUT_OF_SCOPE", "EMPTY_DOCUMENT"] = Field(
        ..., description="범위 판별 상태. CONTRACT_TYPE_UNCERTAIN은 검토 차단이 아닌 경고이며, OUT_OF_SCOPE는 현재 지원 코퍼스와의 공통 근거가 부족함을 뜻한다."
    )
    suggested_contract_type: Optional[str] = Field(
        default=None, description="근거가 충분할 때 제안하는 계약 유형. 최종 선택은 사용자에게 있으며, 제안할 수 없으면 None이다."
    )
    candidates: list[ContractTypeScopeScore] = Field(
        default_factory=list, description="계약 유형별 범위 판별 근거 점수 목록. 점수 내림차순으로 정렬된다."
    )
    matched_clause_count: int = Field(
        default=0, description="지원 범위 카테고리 앵커에 대응된 입력 조항 수. 계약서 전체 조항 수나 적합 확률이 아니다."
    )
    exclusion_markers: list[str] = Field(
        default_factory=list, description="지원 범위 밖 문서를 시사하는 탐지 표식 목록. 비어 있어도 IN_SCOPE를 보장하지 않는다."
    )
    message: Optional[str] = Field(default=None, description="범위 상태의 해석과 권장 다음 단계를 설명하는 보조 메시지.")
