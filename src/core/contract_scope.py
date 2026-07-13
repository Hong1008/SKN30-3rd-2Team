"""파싱된 조항 텍스트만으로 지원 계약 범위를 판별하는 순수 규칙."""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from contracts.enums import Category, ContractType


class ScopeStatus(str, Enum):
    """지원 표준 코퍼스와의 범위 관계."""

    IN_SCOPE = "IN_SCOPE"
    CONTRACT_TYPE_UNCERTAIN = "CONTRACT_TYPE_UNCERTAIN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class ContractScopeAssessment:
    """결정론적 범위 판별의 계산 근거."""

    status: ScopeStatus
    suggested_contract_type: ContractType | None
    scores: dict[ContractType, int]
    matched_clause_count: int
    exclusion_markers: tuple[str, ...]


# 지원 SW 표준계약서와 다른 산업·법령 문서를 명시적으로 가르는 표식이다.
# 파일명은 사용하지 않고 파싱된 본문에 나타난 표식만 사용한다.
_EXCLUSION_MARKERS = (
    "농업", "축산업", "어업", "어업인", "선원", "선박", "승무", "선박소유자",
)

_SW_DOMAIN_MARKERS = (
    "소프트웨어", "프로그램", "시스템 개발", "정보시스템", "유지보수", "유지관리",
    "개발 용역", "개발업무", "개발 업무",
)

_TYPE_MARKERS: dict[ContractType, tuple[str, ...]] = {
    ContractType.SW_FREELANCE: ("프리랜서", "용역", "수탁자"),
    ContractType.SI_SUBCONTRACT: ("하도급", "원사업자", "수급사업자", "발주자"),
    ContractType.SM_SUBCONTRACT: ("유지보수", "유지관리", "운영 업무", "운영업무"),
    ContractType.SW_EMPLOYMENT: ("근로자", "사용자", "근로시간", "근로 계약"),
}


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def assess_contract_scope(clause_texts: Iterable[str]) -> ContractScopeAssessment:
    """조항 텍스트를 지원 코퍼스와 비교해 범위·유형 후보를 계산한다.

    카테고리 앵커는 지원 표준조항의 구조적 공통점을, 유형 앵커는 계약유형을
    구분하는 근거를 제공한다. 이는 검색·규칙만 쓰며 파일명·LLM·외부 I/O에 의존하지 않는다.
    """
    texts = tuple(text.casefold() for text in clause_texts if text and text.strip())
    exclusions = tuple(
        marker for marker in _EXCLUSION_MARKERS
        if _contains_any("\n".join(texts), (marker.casefold(),))
    )
    scores = {contract_type: 0 for contract_type in ContractType}
    matched_clause_count = 0
    domain_clause_count = 0

    for text in texts:
        category_hits = [
            category for category in Category
            if category.anchors and _contains_any(text, (anchor.casefold() for anchor in category.anchors))
        ]
        type_hits = [
            contract_type for contract_type, markers in _TYPE_MARKERS.items()
            if _contains_any(text, (marker.casefold() for marker in markers))
        ]
        has_domain_marker = _contains_any(text, (marker.casefold() for marker in _SW_DOMAIN_MARKERS))

        if category_hits or type_hits or has_domain_marker:
            matched_clause_count += 1
        if has_domain_marker:
            domain_clause_count += 1

        for category in category_hits:
            applicable = category.contract_types or tuple(ContractType)
            for contract_type in applicable:
                scores[contract_type] += 1
        for contract_type in type_hits:
            scores[contract_type] += 2
        if has_domain_marker:
            for contract_type in ContractType:
                scores[contract_type] += 1

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
    best_type, best_score = ranked[0]
    second_score = ranked[1][1]

    if exclusions or domain_clause_count == 0 or best_score == 0:
        status = ScopeStatus.OUT_OF_SCOPE
        suggested = None
    elif best_score >= 4 and best_score - second_score >= 1:
        status = ScopeStatus.IN_SCOPE
        suggested = best_type
    else:
        status = ScopeStatus.CONTRACT_TYPE_UNCERTAIN
        suggested = best_type

    return ContractScopeAssessment(
        status=status,
        suggested_contract_type=suggested,
        scores=scores,
        matched_clause_count=matched_clause_count,
        exclusion_markers=exclusions,
    )
