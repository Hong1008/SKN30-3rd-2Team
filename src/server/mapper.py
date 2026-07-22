"""내부 도메인 결과를 MCP 공개 DTO로 변환한다."""

from collections.abc import Iterable

from contracts.enums import Deviation
from contracts.models import DeviationResult, GroundingLaw, StandardClause
from server.public_dto import (
    CandidateSelected,
    ClauseReviewCandidate,
    MissingStandardCandidate,
    NoCandidate,
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
