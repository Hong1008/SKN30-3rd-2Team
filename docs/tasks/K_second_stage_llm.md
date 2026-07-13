# K — 2차 LLM 제품화

> 현재 유일한 활성 작업이다. 1차 MCP 서버의 동결 계약은 변경하지 않는다.

## 목적

1차가 반환한 검토 후보 중 `NONE`과 `EXTRA`를 서버 밖 데모/클라이언트 LLM이 읽고, 표준 조항과의
실질적 차이 또는 추가 조항 성격을 설명한다. 결과는 언제나 **검토 후보**이며 법률 결론이 아니다.

## 경계

- LLM 호출 위치는 `demo/` 또는 별도 클라이언트다. `src/server/`와 1차 pipe에는 넣지 않는다.
- 입력은 기존 `DeviationResult`의 `user_clause`, `matched_standard`, `confidence`, `toxic_patterns`다.
- 대상은 `NONE`과 `EXTRA`다. `MISSING`과 `NO_MATCH`는 2차 호출 대상이 아니다.
- 2차가 근거가 필요하면 기존 MCP `get_grounding`을 호출한다.

## 구현 순서

1. `NONE` 재확인과 `EXTRA` 설명에 사용할 structured output Pydantic 스키마를 승인한다.
2. LLM provider·모델·실패 시 사용자 표면 동작을 결정한다.
3. `review_contract` 결과에서 대상만 골라 배치 호출하는 데모 글루를 구현한다.
4. 표준 조항 원문, 독소 신호, 근거 자료를 화면에서 출처와 함께 표시한다.

## 완료 조건

- 서버 코드에 LLM import·호출이 없다.
- structured output 파싱 실패와 provider 실패가 명시적인 상태로 사용자에게 전달된다.
- `NONE` 의미 차이 사례와 `EXTRA`의 근접후보 있음/없음 사례를 각각 수동 검증한다.
- 출력은 위법·합법·승소·불리함을 단정하지 않고 검토 후보 프레이밍을 유지한다.

동결된 1차 기준선은 [START_HERE](../START_HERE.md)와 [v5 기준선](../quality/baseline-v5.md)을 따른다.
