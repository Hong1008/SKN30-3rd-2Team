# WorkShield 로드맵

## 활성: K — 2차 LLM 제품화

1차 MCP가 반환한 `NONE`·`EXTRA` 후보를 서버 밖 데모/클라이언트에서 structured output LLM으로 검토한다.
구현 범위와 완료 조건은 [K_second_stage_llm.md](tasks/K_second_stage_llm.md)를 따른다.

## 동결된 1차

v5 기준선은 유지한다. 실험 S는 폐기, C1은 보류이며 추가 튜닝·held-out 재실행은 하지 않는다.
새 1차 개선은 새 데이터, 단일 가설, 사전 승인, 독립 held-out이 모두 있을 때만 별도 로드맵 항목으로 연다.

완료·폐기된 작업 카드는 `archive/tasks/`에, 실험 증빙은 `quality/experiments/`에 보존한다.
