# [재설계 K] 2차 판정 — 잠정 NONE의 의미동치성 최종 확인 (서버 밖 LLM)

> 근거: [07-03 결정 로그](../dicision/07-03.md) §3, 07-07 세션(1차/2차 판정 경계 설계).
> 선행: [J_deviation_redesign.md](J_deviation_redesign.md) — J가 만드는 "잠정 NONE" 신호가 있어야 이 카드가 성립.

## 배경

J 완료 후 `review_contract`(MCP 서버, LLM 무호출)는 매칭된 조항에 대해 커버리지 미달이면 CHANGED를
확정하고, 그 외에는 전부 "잠정 NONE"으로 남긴다. 이 카드는 그 잠정 NONE을 **최종적으로 CHANGED인지
진짜 NONE인지** 확인하는 2차 판정을 구현한다. 대표 사례: 지식재산권 귀속 반전(공동소유→도급인 단독
영구귀속) — 부정어·숫자·당사자 집합이 안 바뀌어 규칙으로도, 리랭커 관련성 점수로도 못 잡지만
원문을 읽으면 명백히 반대 의미다.

## 확정된 설계 (사인오프 완료 — 07-07 세션)

- **호출 위치: 서버 밖(클라이언트/데모 레이어).** MCP 서버 안에 별도 2차 도구를 새로 만들지 않는다
  — `review_contract`를 호출하는 쪽(데모·향후 클라이언트)이 `DeviationResult` 목록을 받아, 그중
  `deviation == NONE`인 항목만 골라 LLM으로 최종 확인한다. 서버 배포 코드에는 LLM 관련 의존성이
  전혀 들어가지 않는다 — AGENTS.md 절대규칙 #1("1차 코드에 LLM 호출 금지")을 문자 그대로 준수.
- **입력은 기존 `DeviationResult` 필드로 충분.** 새 스키마 불필요(J 카드 결정과 동일 원칙) —
  `user_clause`, `matched_standard.text`, `uncovered_sub_chunk_ids`(참고용, NONE 케이스는 항상 `[]`),
  `confidence`만으로 LLM이 두 원문을 직접 비교해 판정.
- **사용자 표면 프레이밍은 "검토 후보"** (AGENTS.md §3) — "위법/합법", "이겼다/졌다" 같은 단정 금지.
  최종 출력도 "확정된 CHANGED" 대신 "재검토 필요"류 표현 권장.

## 구현 대상

1. 2차 판정 함수 설계 (위치: `demo/` 또는 신규 클라이언트 유틸 — **서버 코드(`src/mcp_server` 등)에
   두지 않는다**): 입력 `(user_clause: str, matched_standard_text: str)` → structured output
   (예: `{"final_deviation": "NONE"|"CHANGED", "reason": str}`).
2. Structured output 스키마 확정 — pydantic 모델 또는 JSON 스키마로 LLM 호출 강제(자유 텍스트 금지,
   AGENTS.md §3 프레이밍 유지 위해 근거 문구도 함께 받되 사용자 표면엔 "검토 후보"로만 노출).
3. `review_contract` 반환 목록 중 `deviation == Deviation.NONE`인 항목만 골라 2차에 태우는 배치
   호출 글루 코드(데모 레이어). CHANGED·EXTRA·MISSING·NO_MATCH는 이미 확정이므로 2차 대상 아님.
4. 2차가 CHANGED로 뒤집은 경우, grounding(법령 근거) 부착 필요 여부 검토 — 현재 grounding은
   1차에서 `deviation == CHANGED`일 때만 부착되므로(review_pipe.py), 2차가 뒤집은 케이스는
   grounding이 비어있는 채로 남는다. 이걸 그대로 둘지, 2차 레이어에서 별도로 grounder를 호출할지 결정 필요.

## 미결정 / 사인오프 필요 (AGENTS.md §2)
- ✅ 호출 위치: 서버 밖 (07-07 세션 확정)
- ✅ 입력 스키마: 기존 `DeviationResult` 필드로 충분, 확장 없음 (07-07 세션 확정)
- [ ] 2차 출력 structured schema의 정확한 필드 구성 (reason 필드 필요 여부·형식)
- [ ] 2차가 CHANGED로 뒤집었을 때 grounding·독소 재검사를 다시 돌릴지 여부(§구현대상 4)
- [ ] 2차 판정에 쓸 LLM/모델 선정 — 이 프로젝트가 이미 쓰는 어댑터가 있는지, 데모용으로 별도 도입할지

## 완료 조건 (DoD)
- [ ] 잠정 NONE만 골라 2차로 넘기는 배치 글루 구현
- [ ] 2차 structured output 스키마 확정 + 파싱 검증
- [ ] 서버 코드(MCP 도구)에 LLM 관련 import/호출이 전혀 없음을 재확인(규칙 #1)
- [ ] 사용자 표면 문구가 "검토 후보" 프레이밍인지 확인(규칙 #3)
- [ ] 데모에서 실제 지식재산권 반전류 케이스(예: v3-sw-11)가 2차에서 CHANGED로 뒤집히는지 수동 검증

## 참고
- [07-03 결정 로그](../dicision/07-03.md) · [J_deviation_redesign.md](J_deviation_redesign.md)
- [src/eval/golden/v3_sw_freelance.json](../../src/eval/golden/v3_sw_freelance.json) `v3-sw-11` — 규칙으로 탐지 불가한 대표 사례
- `demo/` 디렉터리 — 기존 데모가 LLM을 호출하는 패턴이 있다면 그 컨벤션 재사용
