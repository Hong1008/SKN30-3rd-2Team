"""MCP 출력 스키마에 DTO 의미가 노출되는지 검증한다."""

from server.dto import ClassifyClauseResponse, MatchCandidate, ReviewContractResponse


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
