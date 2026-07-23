# WorkShield 로드맵

## 현재 활성 개발 작업 없음

1차 MCP 구현과 v5 기준선 검증이 완료됐다. 서버는 외부 클라이언트가
`assess_contract_scope` → `review_contract_candidates` → 필요 시 `get_category_grounding`으로 이어지는
권장 흐름을 사용하도록 제공한다. `review_contract`와 `get_grounding`은 기존 응답 호환용이고,
표준조항 리소스는 독립 탐색·재조회용이다. 특정 2차 LLM 클라이언트의
구현은 현 프로젝트 범위에 포함하지 않는다.

LLM 기반 의미 비교·설명 기능이 별도 제품에서 필요해질 경우에는
[선택적 2차 클라이언트 연동 지침](archive/tasks/K_second_stage_llm.md)을 출발점으로 삼되,
provider·모델·structured output·사용자 경험은 그 클라이언트 소유자가 결정한다.

## 동결된 1차

v5 기준선은 유지한다. 실험 S는 폐기, C1은 보류이며 추가 튜닝·held-out 재실행은 하지 않는다.
새 1차 개선은 새 데이터, 단일 가설, 사전 승인, 독립 held-out이 모두 있을 때만 별도 로드맵 항목으로 연다.

완료·폐기된 작업 카드는 `archive/tasks/`에, 실험 증빙은 `quality/experiments/`에 보존한다.
