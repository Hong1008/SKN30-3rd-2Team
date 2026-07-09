# [재설계 Q] 표준조항 버전(version) 스코핑 미설계 — 검색 풀에 신구 버전 혼재

> 근거: [07-09 결정 로그](../dicision/07-09.md) — `v3_result.md` 재평가 결과 분석 중 실측 발견.
> 선행: 없음. **P_text_normalization.md와 독립**(P는 텍스트 포맷 문제, Q는 버전 스코핑 부재 문제 —
> 서로 다른 축의 원인이 같은 증상(이탈 오분류)에 겹쳐 있었다).
> 이 카드는 **질문 목록만 정리** — 해결책은 착수 세션이 결정.

## 배경 (07-09 실측 요약)

`v3_result.md`(SI_SUBCONTRACT)의 이탈 판정 오분류를 로컬로 재현하던 중 발견:

```
v3-si-41  gold=EXTRA pred=NONE score=0.57   matched=si_subcontract-2022-art36
v3-si-44  gold=EXTRA pred=NONE score=0.9995 matched=si_subcontract-2022-art52
v3-si-45  gold=EXTRA pred=NONE score=0.97   matched=si_subcontract-2025-art14
```

DB 확인 결과 `standard_clauses` 테이블에 SI_SUBCONTRACT 표준조항이 **2022년판(53건)과 2025년판
(56건)이 버전 구분 없이 공존**한다(`SELECT version, COUNT(*) ... GROUP BY version`). 검색·매칭
경로(`_load_standards`(run_eval.py) · `review_contract`의 `type_filter={"contract_type": ...}`)는
`contract_type`만 필터링하고 **`version`은 전혀 걸러내지 않는다** — 두 버전이 같은 검색 풀에서
경쟁한다.

골든 v3는 2025년판 기준으로 작성됐는데, 표준에 없어야 할(EXTRA) 사용자 조항이 옛 2022년판의
유사 조항에 높은 점수로 매칭돼버려 EXTRA가 NONE으로 오분류된다. 이 자체는 오늘 새로 생긴 버그가
아니라 **애초에 "버전"이라는 축이 설계에서 고려된 적이 없어서** 생기는 구조적 결함으로 보이며,
[P_text_normalization.md](P_text_normalization.md)의 헤더/항호 정규화가 조 번호(예: "제36조" vs
"제52조")라는 미약한 구분 신호까지 제거하면서 신구 버전 간 혼동이 더 커졌을 가능성이 있다(정규화가
원인을 만든 게 아니라 기존 결함을 더 드러냈을 가능성).

## 문제 정의 (해결책 아님 — 착수 세션이 설계할 것)

"버전"이 이 시스템에서 정확히 무엇을 의미해야 하는지 자체가 미정이다:
- 사용자가 검토를 요청한 계약서는 항상 **최신 표준(예: SI_SUBCONTRACT는 2025년판)**과만 비교되어야
  하는가? 아니면 특정 시점 계약을 검토할 때 그 시점의 표준(예: 2022년판 기준 체결 계약)과 비교할
  선택지도 필요한가?
- `StandardClause.version` 필드(`data/03_normalized/standard_clauses.*.json`)는 이미 존재하지만
  **검색·매칭 어디에서도 실제로 소비되지 않는다** — 지금까지는 그냥 메타데이터로만 적재돼 있었다.
- 여러 버전을 동시에 유지하는 이유 자체가 뭔지 재확인 필요(예: SI/SM은 2022년판·2025년판 둘 다
  `data/03_normalized`에 있음 — 과거 버전과의 비교/마이그레이션 지원 목적인지, 단순히 정리가 안 된
  상태인지).

## 검토할 방향 (07-09에서 거론 — 순위·선택은 착수 세션 몫)

1. **최신 버전만 검색 풀에 포함**(기본값): `review_contract`/`_load_standards` 호출 시
   계약유형별 최신 `version`만 조회하도록 필터 추가. 가장 단순하고 골든 v3(2025년판 기준) 문제를
   바로 해소하지만, "특정 시점 표준과 비교" 유스케이스를 원천 차단.
2. **호출자가 `version`을 명시 지정**: `review_contract`/MCP 시그니처(`server.py`)에 `version`
   파라미터 추가(동결 계약 확장 — AGENTS.md §2, 사람 승인 필요), 생략 시 최신판 기본.
3. **버전을 유사도 매칭에서 배제하되 결과에는 노출**: 검색은 최신판으로 제한하되, 매칭 결과에
   `matched_standard.version`을 사용자에게 노출해 "이 표준은 2025년판 기준"임을 명시(현재도
   `StandardClause.version` 필드는 있으니 노출 자체는 가능 — 검색 스코핑만 빠진 상태).

## 미결정 / 사인오프 필요 (AGENTS.md §2)

- [ ] "버전"의 의미(질문 목록 상단) 자체를 먼저 확정 — 이게 정해져야 방향 1~3 중 선택 가능.
- [ ] 방향 2 채택 시 `review_contract`/MCP 도구 시그니처 확장 여부 — 동결 계약 변경이라 사람 승인
      선행.
- [ ] 구버전(2022년판) 데이터를 검색 풀에서 뺄 뿐 `data/03_normalized`에서 삭제할지, 보관만 할지.

## 완료 조건 (DoD)

- [ ] "버전"의 용도·의미 확정(질문 목록 상단)
- [ ] 채택 방향 확정 + 구현
- [ ] [L_golden_v3.md](L_golden_v3.md) 골든셋으로 SI/SM 이탈 오분류(v3-si-41·44·45 등) 재측정,
      해소됐는지 확인
- [ ] LLM 없이 검색·매칭만(규칙 #1), 지표는 결정론(규칙 #5)

## 참고
- [07-09 결정 로그](../dicision/07-09.md) — 실측 경위·재현 데이터
- [P_text_normalization.md](P_text_normalization.md) — 같은 세션에서 발견된 별개 축의 원인
- [src/eval/run_eval.py](../../src/eval/run_eval.py) `_load_standards`
- [src/pipe/review_pipe.py](../../src/pipe/review_pipe.py) `review_contract`의 `type_filter`
- [src/contracts/models.py](../../src/contracts/models.py) `StandardClause.version`
