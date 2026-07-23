"""기존 Python import 경로를 보존하는 DTO 호환 모듈.

MCP 구현은 공개 계약을 ``server.public_dto``에서, 도메인 결합 호환 계약을
``server.legacy_dto``에서 직접 가져온다. 외부 코드의 기존 import만 이 모듈로 재노출한다.
"""

from server.legacy_dto import (
    ClassifyClauseResponse,
    GetGroundingResponse,
    ParseContractResponse,
    ReviewContractResponse,
)
from server.public_dto import (
    AssessContractScopeResponse,
    CategoryInfo,
    ContractTypeScopeScore,
    ListCategoriesResponse,
    ListContractTypesResponse,
    ListToxicPatternDetailsResponse,
    ListToxicPatternsResponse,
    MatchCandidate,
    MatchClauseResponse,
    ToxicPatternDetail,
)

__all__ = [
    "AssessContractScopeResponse",
    "CategoryInfo",
    "ClassifyClauseResponse",
    "ContractTypeScopeScore",
    "GetGroundingResponse",
    "ListCategoriesResponse",
    "ListContractTypesResponse",
    "ListToxicPatternDetailsResponse",
    "ListToxicPatternsResponse",
    "MatchCandidate",
    "MatchClauseResponse",
    "ParseContractResponse",
    "ReviewContractResponse",
    "ToxicPatternDetail",
]
