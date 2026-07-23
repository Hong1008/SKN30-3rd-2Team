"""내부 도메인 결과를 MCP 공개 DTO로 변환한다."""

from collections.abc import Iterable

from contracts.enums import Deviation
from contracts.models import DeviationResult, GroundingLaw, StandardClause
from server.legacy_dto import ClassifyClauseResponse, ParseContractResponse
from server.public_dto import (
    CandidateSelected,
    ClassifyClauseCandidateResponse,
    ClauseReviewCandidate,
    MissingStandardCandidate,
    NoCandidate,
    ParseContractClausesResponse,
    PublicClause,
    PublicGroundingLaw,
    PublicStandardClause,
    ReviewContractCandidatesResponse,
)


def to_public_grounding_laws(laws: Iterable[GroundingLaw]) -> list[PublicGroundingLaw]:
    """내부 법령 모델을 독립된 공개 DTO로 복사한다."""
    return [
        PublicGroundingLaw(
            법령명=law.법령명,
            조번호=law.조번호,
            본문=law.본문,
            출처=law.출처,
        )
        for law in laws
    ]


def to_parse_contract_clauses_response(
    response: ParseContractResponse,
) -> ParseContractClausesResponse:
    """도메인 Clause를 공개 조항 DTO로 복사한다."""
    return ParseContractClausesResponse(
        status=response.status,
        contract_type=response.contract_type,
        clauses=[
            PublicClause(idx=clause.idx, num=clause.num, title=clause.title, text=clause.text)
            for clause in response.clauses
        ],
        message=response.message,
    )


def _to_public_standard(standard: StandardClause) -> PublicStandardClause:
    """내부 표준조항을 외부 공개 모델로 복사한다."""
    return PublicStandardClause(
        clause_id=standard.clause_id,
        contract_type=standard.contract_type.value,
        category=standard.category.value,
        title=standard.title,
        text=standard.text,
        source=standard.source,
        version=standard.version,
    )


def to_classify_clause_candidate_response(
    response: ClassifyClauseResponse,
) -> ClassifyClauseCandidateResponse:
    """기존 내부 단일 조항 결과에서 법령 필드를 제거한 공개 DTO를 만든다."""
    return ClassifyClauseCandidateResponse(
        status=response.status,
        contract_type=response.contract_type,
        deviation=response.deviation,
        confidence=response.confidence,
        matched_standard=(
            _to_public_standard(response.matched_standard)
            if response.matched_standard is not None
            else None
        ),
        message=response.message,
    )


def to_review_contract_candidates_response(
    *,
    status: str,
    contract_type: str,
    results: Iterable[DeviationResult],
    message: str | None = None,
) -> ReviewContractCandidatesResponse:
    """기존 파이프라인 결과를 법령 없는 공개 검토 계약으로 변환한다."""
    clause_results: list[ClauseReviewCandidate] = []
    missing_standard_clauses: list[MissingStandardCandidate] = []

    for result in results:
        if result.deviation == Deviation.MISSING:
            if result.matched_standard is None:
                raise ValueError("MISSING 결과에는 누락된 표준조항이 필요합니다.")
            missing_standard_clauses.append(
                MissingStandardCandidate(standard=_to_public_standard(result.matched_standard))
            )
            continue

        match = (
            CandidateSelected(
                status="CANDIDATE_SELECTED",
                standard=_to_public_standard(result.matched_standard),
                score=result.confidence,
            )
            if result.matched_standard is not None
            else NoCandidate(status="NO_CANDIDATE")
        )
        clause_results.append(
            ClauseReviewCandidate(
                user_clause=result.user_clause,
                deviation=result.deviation.value,
                match=match,
                toxic_patterns=[pattern.value for pattern in result.toxic_patterns],
            )
        )

    return ReviewContractCandidatesResponse(
        status=status,
        contract_type=contract_type,
        clause_results=clause_results,
        missing_standard_clauses=missing_standard_clauses,
        message=message,
    )
