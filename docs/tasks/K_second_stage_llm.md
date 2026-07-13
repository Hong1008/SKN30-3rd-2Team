# [재설계 K] 2차 판정 — 잠정 NONE·EXTRA의 최종 확인/설명 (서버 밖 LLM)

> **현재 상태: backlog / 미착수.** 1차 품질 진단과 v4 독립 검증 뒤 진행한다. structured output
> 스키마와 모델 사인오프 전에는 구현하지 않으며, MCP 서버 안에는 LLM 호출을 넣지 않는다.

> 근거: [07-03 결정 로그](../dicision/07-03.md) §3, 07-07 세션(1차/2차 판정 경계 설계).
> 선행: [J_deviation_redesign.md](J_deviation_redesign.md) — J가 만드는 "잠정 NONE"/근접후보 포함 EXTRA 신호가 있어야 이 카드가 성립.
>
> **⚠ 2026-07-08 확장 개정**: J가 이후 세션에서 원안보다 더 크게 단순화됐다(`CHANGED` enum 값 자체가
> 폐지됨, 서브청크 커버리지 2패스도 전체 삭제). 아래는 그 확장된 J를 전제로 다시 쓴 버전이다 —
> "배경"·"확정된 설계"·"구현대상"이 원래 문서와 달라졌으니 과거 버전을 참고하지 말 것.

## 배경

확장된 J 이후 `review_contract`(MCP 서버, LLM 무호출)의 1차 판정은 `select_best_match` 단일
임계값(`match_threshold`) 기준으로 끝난다 — 커버리지 체크도, 규칙기반 치명변경 탐지도 없다.

- `score >= match_threshold` → `NONE` (잠정 — "표준과 매칭됨"이라는 뜻일 뿐, 내용까지 같다는
  확정이 아니다)
- `score < match_threshold` (그러나 후보 자체는 있음) → `EXTRA` — 이제 `matched_standard`가
  **채워진 채로** 반환된다(`select_best_match`가 임계값과 무관하게 항상 최고점 후보를 반환하도록
  바뀜, `core/matching.py`). 즉 EXTRA도 "무엇과 비교해 다른지"를 알 수 있다.
- 후보 자체가 없음 → `NO_MATCH` (변경 없음)
- 표준조항이 아예 매칭 안 됨 → `MISSING` (변경 없음)

대표 사례(NONE 재확인 필요): 지식재산권 귀속 반전(공동소유→도급인 단독 영구귀속) — 부정어·숫자·
당사자 집합이 안 바뀌어 규칙으로도, 리랭커 관련성 점수로도 못 잡지만 원문을 읽으면 명백히 반대
의미다(`v3-sw-11`).

대표 사례(EXTRA 설명 필요): 표준에 없는 완전 신규 조항인지, 아니면 표준과 근접했지만 임계값을
못 넘을 만큼 크게 달라진 변형인지는 1차가 구분하지 못한다 — `matched_standard`가 있으면 후자,
없으면 전자에 가깝다는 정도만 1차가 신호로 줄 수 있다.

## 확정된 설계 (사인오프 완료 — 07-07 세션 + 2026-07-08 세션)

- **호출 위치: 서버 밖(클라이언트/데모 레이어).** MCP 서버 안에 별도 2차 도구를 새로 만들지 않는다.
  서버 배포 코드에는 LLM 관련 의존성이 전혀 들어가지 않는다 — AGENTS.md 절대규칙 #1을 문자 그대로
  준수. (변경 없음)
- **입력은 기존 `DeviationResult` 필드로 충분.** `uncovered_sub_chunk_ids` 필드는 커버리지 체크
  제거로 이미 삭제됐다(참조하지 말 것). `user_clause`, `matched_standard`(EXTRA도 근접후보가
  있으면 채워짐), `toxic_patterns`, `confidence`만으로 LLM이 판단.
- **2차 대상은 이제 `NONE` + `EXTRA` 둘 다** (2026-07-08 세션에서 확장 — 원래는 NONE만이었음):
  - **NONE 재확인**: `user_clause` vs `matched_standard.text` 비교 → "진짜 동일" vs "실질적으로
    다름".
  - **EXTRA 설명**: "표준과 내용차이가 큰 변경"인지 "완전히 새로운 추가조항"인지 설명. 단,
    **독소조항 여부는 이미 1차가 결정론적으로 판정**해 `toxic_patterns` 필드에 채워두므로(별도
    벡터 검색+임계값, LLM 아님), 2차가 처음부터 판단할 3분류가 아니라 **2분류**(내용차이 큰 변경 /
    완전 추가조항)+독소 신호는 1차 필드를 그대로 인용하면 된다.
  - `MISSING`·`NO_MATCH`는 2차 대상 아님 — `MISSING`은 이미 확정 사실(비교할 `user_clause` 자체가
    없음), `NO_MATCH`는 비교 대상 자체가 없음.
- **grounding은 2차가 필요할 때 직접 호출해야 한다(선택이 아니라 구조적 필연).** 현재 1차는
  `MISSING`에만 grounding을 붙이며 `NONE`/`EXTRA` 및 독소 패턴에는 `grounding=[]`다. 독소 전용
  grounding은 아직 구현 범위 밖이다. 2차가 NONE을 "실질적 차이"로 설명하거나 EXTRA를
  "내용차이 큰 변경"으로 설명하면서 근거가 필요하면, 기존 MCP 도구
  `get_grounding(category, contract_type)`을 그대로 재사용해 직접 호출한다(서버 코드 수정 불필요 —
  이미 있는 도구).
- **사용자 표면 프레이밍은 "검토 후보"** (AGENTS.md §3) — "위법/합법", "이겼다/졌다" 같은 단정 금지.
  (변경 없음)

## 구현 대상

1. 2차 판정 함수 설계 (위치: `demo/` 또는 신규 클라이언트 유틸 — **서버 코드에 두지 않는다**).
   두 트랙:
   - NONE 재확인: 입력 `(user_clause, matched_standard.text)` → structured output.
   - EXTRA 설명: 입력 `(user_clause, matched_standard?, toxic_patterns)` → structured output.
     `matched_standard`가 없으면(진짜 후보 자체가 없던 EXTRA) 비교 없이 "완전 추가조항"으로 귀결.
2. Structured output 스키마 확정 — **미정, 2차 실제 착수 시 결정** (아래 "미결정" 참조). 기존
   `demo/src/llm/schemas.py`의 `StructuredSummary`/`Finding`(`provider.parse(..., response_format=)`
   패턴)을 참고해 재사용할 수 있다.
3. `review_contract` 반환 목록 중 `deviation in (Deviation.NONE, Deviation.EXTRA)`인 항목을 골라
   2차에 태우는 배치 호출 글루 코드(데모 레이어). `MISSING`·`NO_MATCH`는 제외.
4. ~~2차가 CHANGED로 뒤집은 경우 grounding 부착 필요 여부 검토~~ → **위 "확정된 설계"에서 이미
   결론남**: 1차가 NONE/EXTRA엔 grounding을 붙이지 않으므로, 2차가 설명할 때 필요하면
   기존 `get_grounding` 도구를 직접 부르면 된다. 별도 결정 불필요.

## 미결정 / 사인오프 필요 (AGENTS.md §2)
- ✅ 호출 위치: 서버 밖 (07-07 세션 확정)
- ✅ 입력 스키마: 기존 `DeviationResult` 필드로 충분, 확장 없음 (07-07 세션 확정)
- ✅ 2차 대상 범위: NONE + EXTRA 둘 다 (2026-07-08 세션 확정, 원래는 NONE만이었음)
- ✅ grounding 재조회 방식: 1차가 안 붙이므로 2차가 기존 `get_grounding` 도구를 직접 호출
  (2026-07-08 세션 확정 — §구현대상 4 참조)
- [ ] 2차 출력 structured schema의 정확한 필드 구성(reason 필드 형식, NONE/EXTRA 두 트랙을 스키마
  하나로 합칠지 나눌지, 최종 라벨 이름을 1차 enum과 헷갈리지 않게 뭐라고 부를지 — 예: `"CHANGED"`
  대신 `"DIFFERS"`) — **2차 실제 착수 시 결정하기로 명시적으로 미룸** (사용자 확인)
- [ ] 2차 판정에 쓸 LLM/모델 선정 — `demo/src/llm/providers.py`의 `build_provider()`를 그대로
  재사용할지, 배치 판정용으로 별도 provider를 쓸지 — **2차 실제 착수 시 결정하기로 명시적으로 미룸**

## 완료 조건 (DoD)
- [ ] 잠정 NONE + EXTRA(근접후보 有無 모두)를 골라 2차로 넘기는 배치 글루 구현
- [ ] 2차 structured output 스키마 확정 + 파싱 검증
- [ ] 서버 코드(MCP 도구)에 LLM 관련 import/호출이 전혀 없음을 재확인(규칙 #1)
- [ ] 사용자 표면 문구가 "검토 후보" 프레이밍인지 확인(규칙 #3)
- [ ] 데모에서 실제 지식재산권 반전류 케이스(예: `v3-sw-11`, 현재 골든셋엔 `gold_deviation: NONE`
  으로 재라벨링됨)가 2차에서 "실질적 차이"로 뒤집히는지 수동 검증
- [ ] EXTRA 설명 트랙: `matched_standard`가 있는 EXTRA와 없는 EXTRA 각각 한 사례씩 수동 검증

## 참고
- [07-03 결정 로그](../dicision/07-03.md) · [J_deviation_redesign.md](J_deviation_redesign.md)
- [src/eval/golden/v3_sw_freelance.json](../../src/eval/golden/v3_sw_freelance.json) `v3-sw-11` — 규칙으로 탐지 불가한 대표 사례(현재 `gold_deviation: NONE`)
- `demo/src/llm/agent.py`·`schemas.py`·`providers.py` — 기존 `summarize()`가 쓰는
  `provider.parse(messages, response_format=<pydantic 모델>)` 구조화 출력 패턴 재사용 권장
- `match_clause` MCP 도구(`server.py`) — 초기 설계 검토 중 "EXTRA엔 비교 대상이 없으니 이 도구를
  2차가 재호출해 근접후보를 얻자"는 안이 나왔었으나, `select_best_match`가 임계값과 무관하게 항상
  최고점 후보를 반환하도록 바뀌면서(위 "배경" 참조) 불필요해짐 — `DeviationResult.matched_standard`
  만으로 충분.
