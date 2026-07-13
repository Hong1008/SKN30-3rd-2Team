# K — 선택적 2차 클라이언트 연동 지침

> 상태: archive · 현 프로젝트의 활성 구현 작업이 아님

## 결정

WorkShield 1차 MCP는 외부 클라이언트가 표준 대비 검토 후보와 근거 자료를 소비할 수 있는 상태로
완료·동결됐다. 따라서 이 프로젝트는 특정 2차 LLM 클라이언트, provider, 모델, structured output
스키마 또는 UI를 구현·강제하지 않는다.

이 문서는 향후 별도 제품이나 외부 소비자가 WorkShield MCP 위에 LLM 기반 설명 기능을 만들 때 참고할
선택적 연동 지침이다. 현재 제품 명세나 다음 작업 지시가 아니다.

## MCP가 제공하는 클라이언트 독립 인터페이스

- `review_contract`는 `NONE`·`EXTRA`·`MISSING`·`NO_MATCH` 신호, 사용자 조항, 대응 표준조항,
  confidence, 독소 패턴, 가능한 근거 자료를 구조화해 반환한다.
- `get_grounding`은 카테고리 또는 조항 본문을 바탕으로 관련 법령 원문을 조회하며 `OK`·`NO_RESULT`·
  `INVALID_INPUT` 상태를 반환한다.
- `standard://{contract_type}` 및 `standard://{contract_type}/{clause_id}` 리소스는 표준조항 목록과
  원문을 읽기 전용으로 제공한다.
- 법령·판례 프록시 도구는 필요한 외부 클라이언트가 추가 근거 자료를 조회할 수 있도록 제공된다.

도구·리소스 목록, 상태 처리, 계약유형 선택 흐름은 [server MCP 통합 가이드](../../../src/server/README.md)를
기준으로 한다.

## 선택적 LLM 클라이언트의 책임

LLM을 사용하는 클라이언트는 자체 제품 요구에 맞춰 provider, 모델, 출력 스키마, 실패 처리, 사용자
경험과 검증 방식을 결정한다. 이 선택은 MCP 계약 또는 1차 평가 기준을 바꾸지 않는다.

- 의미 차이 설명이 필요하면 `NONE`과 `EXTRA`의 사용자 조항·대응 표준조항을 소비할 수 있다.
- `MISSING`과 `NO_MATCH`는 1차의 명시 상태이며, LLM이 이를 재분류하거나 근거 없이 보완하지 않는다.
- 추가 근거가 필요할 때만 `get_grounding` 또는 법령 프록시를 호출한다. 반환 상태가 실패·미확인이면
  추정으로 대체하지 않는다.
- `Deviation`과 `toxic_patterns`는 독립 축이다. `EXTRA`를 독소로, 빈 독소 목록을 안전으로 해석하지
  않는다.
- 사용자 표면에는 위법·합법·승소·유불리를 단정하지 않고, 표준 대비 **검토 후보** 및 참고 자료로
  표현한다.
- 계약 원문·개인정보 전달을 최소화하고, LLM 호출·근거 조회의 권한, 호출량, 보존 정책은 해당
  클라이언트가 정한다.

## 비범위

- `src/contracts`, `src/core`, `src/adapter`, `src/pipe`, `src/server`에 LLM 호출을 추가하지 않는다.
- 1차의 v5 기준선, 임계값, 검색·매칭·독소 패턴을 2차 클라이언트 요구로 조정하지 않는다.
- 과거 `demo/` Streamlit 구현은 deprecated된 시연 예시이며, 이 지침의 참조 구현이 아니다.

1차의 현재 상태와 동결 기준은 [START_HERE](../../START_HERE.md) 및
[v5 기준선](../../quality/baseline-v5.md)을 따른다.
