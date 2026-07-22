"""클라이언트가 WorkShield 권장 MCP 흐름을 발견하는 도구."""

from server.capability_dto import (
    GetMcpCapabilitiesResponse,
    LegacyToolReplacement,
    ToolWorkflow,
)


def get_mcp_capabilities() -> GetMcpCapabilitiesResponse:
    """권장 검토 흐름과 기존 호환 도구의 대체 관계를 구조화해 반환합니다.

    신규 클라이언트는 이 결과의 workflows를 기본 호출 순서로 사용하세요. legacy_replacements의
    기존 도구는 삭제되지 않았지만 내부 도메인 결합 또는 모호한 빈 필드를 유지하므로 신규 연동에는
    권장하지 않습니다. 이 도구는 계약서나 법령을 조회하지 않습니다.
    """
    return GetMcpCapabilitiesResponse(
        schema_version="1.0",
        product_boundary=(
            "표준 대비 검토 후보와 참고 근거를 제공하며 위법·합법, 계약상 유불리 또는 승소 가능성을 "
            "확정하지 않습니다."
        ),
        workflows=[
            ToolWorkflow(
                name="FULL_CONTRACT_REVIEW",
                description="계약 유형을 확인하고 법령 조회와 분리된 전체 검토 후보를 생성합니다.",
                steps=[
                    "assess_contract_scope",
                    "review_contract_candidates",
                    "get_category_grounding",
                ],
            ),
            ToolWorkflow(
                name="SELECTED_CLAUSE_REVIEW",
                description="계약서를 공개 DTO로 파싱한 뒤 선택한 조항만 표준과 비교합니다.",
                steps=["parse_contract_clauses", "classify_clause_candidate"],
            ),
            ToolWorkflow(
                name="STANDARD_BROWSING",
                description="전체 검토와 독립적으로 표준조항 후보를 검색하거나 리소스를 조회합니다.",
                steps=["list_contract_types", "match_clause"],
            ),
        ],
        legacy_replacements=[
            LegacyToolReplacement(
                legacy_tool="parse_contract",
                recommended_tool="parse_contract_clauses",
                reason="내부 Clause 모델 대신 독립된 공개 DTO를 반환합니다.",
            ),
            LegacyToolReplacement(
                legacy_tool="review_contract",
                recommended_tool="review_contract_candidates",
                reason="법령 조회와 검토를 분리하고 MISSING 결과를 별도 배열로 반환합니다.",
            ),
            LegacyToolReplacement(
                legacy_tool="classify_clause",
                recommended_tool="classify_clause_candidate",
                reason="조회하지 않은 grounding 빈 필드를 공개 응답에서 제거합니다.",
            ),
            LegacyToolReplacement(
                legacy_tool="get_grounding",
                recommended_tool="get_category_grounding",
                reason="미매핑·검색 결과 없음·외부 오류·시간 초과를 구분합니다.",
            ),
        ],
        legal_proxy_note=(
            "search_law 등 외부 법령·판례 프록시의 결과는 참고 자료이며, 특정 계약에 대한 법률적 결론으로 "
            "사용하지 않습니다."
        ),
    )
