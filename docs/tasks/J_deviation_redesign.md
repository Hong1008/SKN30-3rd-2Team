# [재설계 J] NONE/CHANGED 판정 — 규칙기반 치명변경 탐지 제거 + 잠정 NONE 재정의

> 근거: [07-03 결정 로그](../dicision/07-03.md) §2·§3, 07-07 세션(1차/2차 판정 경계 설계).
> 선행: 없음(core/pipe 순수 리팩터, 즉시 착수 가능). **K·M 의 전제 조건.**

## 배경 — 왜 규칙 계층을 없애는가

`core/deviation.py`의 `detect_critical_changes`(부정어·숫자·당사자 정규식)는 v3 골든셋 작성 중 세 가지
실패가 실측됐다: ①"아니 된다"(되≠된, 유니코드 문자 차이) 미탐지 ②숫자 뒤 조사 "을"을 당사자로 오탐
③"없다/없이"(모달 불가능 부정) 완전 미커버. 게다가 지식재산권 귀속 반전(공동소유→단독귀속) 같은
**부정어·숫자·당사자 집합 자체가 안 바뀌는 순수 의미 반전**은 정규식으로 원리상 탐지 불가능함도
확인됨(v3 `v3-sw-11`). 개별 패치는 끝나지 않는 두더지잡기이므로, 이 계층 전체를 없애고 그 자리를
2차(LLM, 이 프로젝트 서버 밖)로 넘기기로 확정함.

## 확정된 설계 (사인오프 완료 — 07-07 세션)

- **규칙기반 치명변경 탐지(`detect_critical_changes`, `_NEGATION_RE`, `_NUMBER_RE`, `_PARTY_RE`,
  `CRITICAL_NEGATION`/`CRITICAL_NUMBER`/`CRITICAL_PARTY`) 완전 제거.** 축소·보강 아님 — 삭제.
- **difflib 폴백 경로도 동일 원리로 제거.** `classify_clause_deviation`이 서브청크 미주입 등으로
  커버리지 체크를 못 할 때 `calculate_text_similarity`+`change_threshold`로 NONE/CHANGED를 가르던
  로직도 같은 구조적 한계(글자일치율 ≠ 의미동치성)를 공유하므로 함께 제거.
  → **커버리지 불가 시 무조건 CHANGED**(안전측, 2차로 넘김)로 단순화.
- **`DeviationResult`에 새 필드 추가 없음.** 2차가 필요한 정보(`user_clause`, `matched_standard.text`,
  `uncovered_sub_chunk_ids`, `confidence`)는 이미 다 있음 — 최소주의 채택.
- **`Deviation` enum 값 자체는 무변경**(`NONE`/`CHANGED`/`EXTRA`/`MISSING`/`NO_MATCH` 그대로).
  다만 **`NONE`의 의미를 문서상 재정의**: "의미 동치 확정"이 아니라 **"1차 결정론 신호로는 이견 없음
  (잠정), 최종 확정은 2차 몫"**. `CHANGED`는 그대로 최종 확정 값(아래 판정표 참조).

## 새 판정표 (매칭 성공 조항 기준 — 2026-07-07 재정의)

| 조건 | 판정 결과 | 설명 |
| --- | --- | --- |
| 검색 후보가 아예 없음 | **NO_MATCH** | 1차 결정론 단계에서 매칭 실패 (빈 응답 금지 표식) |
| 후보는 있으나 score < match_threshold | **EXTRA** | 1차 결정론 단계에서 대응 불가 (2차 LLM에서 분석) |
| score >= match_threshold | **NONE (잠정)** | 1차 매칭 성공 (실제 의미 일치 여부는 2차 LLM에서 검토) |

즉 "커버리지 미달 → CHANGED"만 결정론으로 남고, 나머지는 전부 "2차 확인이 필요한 잠정 NONE"으로
수렴한다. **CHANGED로 확정되는 케이스가 줄고 잠정 NONE이 늘어나는 것은 의도된 방향**이다 — 애매하면
확정하지 말고 2차에 넘기는 게 안전하다는 원칙(AGENTS.md §3 "검토 후보" 프레이밍)과 부합.

## 구현 대상

1. `src/core/deviation.py`: `CRITICAL_NEGATION`/`CRITICAL_NUMBER`/`CRITICAL_PARTY` 상수,
   `_NEGATION_RE`/`_NUMBER_RE`/`_PARTY_RE`/`_content_numbers`/`detect_critical_changes` 전부 제거.
   `core/__init__.py`의 관련 export도 정리.
2. `classify_clause_deviation`: `detect_critical_changes` 호출 제거. difflib 폴백 분기 삭제 →
   커버리지 불가 시 `Deviation.CHANGED` 반환으로 대체(위 판정표 4행).
3. `src/pipe/review_pipe.py`: 2차 패스에서 `detect_critical_changes(clause.text, matched_standard.text)`
   호출하던 부분 제거. 커버리지 충족 시 곧바로 `Deviation.NONE`(잠정) 반환.
4. `DeviationResult.deviation` docstring(`contracts/models.py`)에 "NONE=1차 잠정, 최종 아님" 의미 추가
   (필드 추가 아님, 주석만).
5. 삭제되는 함수를 참조하던 테스트(`tests/core/test_deviation.py`의 negation/number/party 관련 테스트,
   `tests/pipe/test_review_pipe.py`의 관련 케이스) 정리 — 삭제된 동작은 테스트도 삭제, 남는 동작
   (커버리지 미달→CHANGED, 커버리지 불가→CHANGED)은 새 테스트로 명세.

## 미결정 / 사인오프 필요 (AGENTS.md §2)
- ✅ 규칙계층 완전 제거 (07-07 세션 확정)
- ✅ difflib 폴백도 함께 제거 (07-07 세션 확정)
- ✅ `DeviationResult` 필드 확장 없음 (07-07 세션 확정)
- ✅ `uncovered_sub_chunk_ids` 필드 삭제 (07-07 세션 확정)
- [ ] K·M 카드는 이 변경으로 전제가 완전히 바뀌었으니 착수 전 반드시 재확인 필요.


## 완료 조건 (DoD)
- [ ] 규칙기반 치명변경 탐지·difflib 폴백 코드 삭제, 참조하는 곳 전부 정리
- [ ] 새 판정표대로 `classify_clause_deviation`/`review_pipe.py` 동작 확인
- [ ] `uv run pytest tests/core/ tests/pipe/` 통과 (삭제분 반영한 테스트로 갱신)
- [ ] LLM 호출 없음(규칙 #1), `DeviationResult` 계약 필드 변경 없음 재확인

## 참고
- [07-03 결정 로그](../dicision/07-03.md) — 명제 합의 배경
- [src/core/deviation.py](../../src/core/deviation.py) · [src/pipe/review_pipe.py](../../src/pipe/review_pipe.py)
- 후속: [K_second_stage_llm.md](K_second_stage_llm.md)(이 카드가 만든 잠정 NONE을 소비), [M_eval_dual_track.md](M_eval_dual_track.md)(채점 방식 재정의)

---
### 2026-07-07 확장 결정
원래의 좁은 범위(CHANGED 유지, enum 무변경)에서 아키텍처 단순화를 위해 **CHANGED 폐지 및 커버리지 2패스 메커니즘 전체 삭제**로 범위가 확장되었습니다. 1차 판정(결정론 단계)은 `select_best_match`를 통한 단일 매칭 게이트로 수렴되며, 모든 세부 의미 비교와 이탈 해석은 2차 LLM 패스로 위임됩니다.
