"""MCP 출력 스키마에 DTO 의미가 노출되는지 검증한다."""

from server.dto import ClassifyClauseResponse, MatchCandidate, ReviewContractResponse
from server.public_dto import GetCategoryGroundingResponse, ReviewContractCandidatesResponse


def test_response_fields_expose_descriptions_in_json_schema():
    """Pydantic 필드 설명은 MCP outputSchema로 전달되는 JSON Schema에 포함되어야 한다."""
    schema = ClassifyClauseResponse.model_json_schema()

    assert "MISSING은 전체 계약서 비교" in schema["properties"]["deviation"]["description"]
    assert "법률적 결론" in schema["properties"]["confidence"]["description"]
    assert "항상 빈 목록" in schema["properties"]["grounding"]["description"]


def test_nested_response_dto_fields_expose_descriptions_in_json_schema():
    """중첩 DTO와 전체 검토 응답도 에이전트가 해석할 설명을 제공해야 한다."""
    candidate_schema = MatchCandidate.model_json_schema()
    review_schema = ReviewContractResponse.model_json_schema()

    assert "판정 임계값" in candidate_schema["properties"]["score"]["description"]
    assert "status와 함께 해석" in review_schema["properties"]["results"]["description"]


def test_review_candidates_schema_is_independent_from_legacy_domain_models():
    """신규 공개 계약은 내부 DeviationResult와 grounding 필드를 노출하지 않는다."""
    schema = ReviewContractCandidatesResponse.model_json_schema()

    assert "DeviationResult" not in schema.get("$defs", {})
    assert "GroundingLaw" not in schema.get("$defs", {})
    assert "grounding" not in str(schema)
    assert "related_risk_clauses" not in str(schema)
    assert set(schema["properties"]) == {
        "status",
        "contract_type",
        "clause_results",
        "missing_standard_clauses",
        "message",
    }


def test_category_grounding_schema_exposes_explicit_lookup_states():
    """조회하지 않음·미매핑·검색 결과 없음·통신 실패를 빈 배열 하나로 합치지 않는다."""
    schema = GetCategoryGroundingResponse.model_json_schema()

    assert set(schema["properties"]) == {
        "status",
        "category",
        "contract_type",
        "grounding",
        "message",
    }
    assert set(schema["properties"]["status"]["enum"]) == {
        "OK",
        "NO_RESULT",
        "UNMAPPED_CATEGORY",
        "UPSTREAM_ERROR",
        "TIMEOUT",
    }
    assert "OK일 때만" in schema["properties"]["grounding"]["description"]
