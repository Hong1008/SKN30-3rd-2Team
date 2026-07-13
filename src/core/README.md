# src/core/ — 이탈 탐지 알고리즘 (순수 함수 · TDD 대상)

WorkShield의 **핵심 기여**(기획서 7장). "표준 대비 이탈을 탐지"하는 로직이 여기 모입니다.

> 원칙: **순수 함수.** I/O 없음(DB·네트워크·파일 접근 금지), 부수효과 없음. 같은 입력 → 항상 같은 출력. 그래서 **테스트로 규격을 고정**하기 가장 좋은 곳입니다 → 팀원은 미리 작성된 테스트를 통과시키면 끝.

DB 조회·임베딩 같은 외부 작업이 필요하면 **인자로 받습니다**(adapter를 직접 import 하지 않음). 조립은 `pipe/`가 담당합니다.

---

## 파이프라인 속 위치

```
[retriever] top-k 후보 반환
      ↓
select_best_match()          ← 리랭커 점수 기준 최고 후보 선택 (임계치 미적용)
      ↓
[pipe] 후보 0개이면 NO_MATCH 직접 처리  ← core가 아닌 pipe 책임
      ↓
classify_clause_deviation()  ← EXTRA / NONE 확정
      ↓
detect_missing_clauses()     ← 루프 종료 후 한 번, MISSING 확정
      ↓
traverse_related_risks()     ← 표준조항의 연관 조항 추적용 순수 함수 (고도화 A)
detect_toxic_patterns()      ← 동일 조항에 대해 독소 패턴 역방향 검색 (고도화 B)
```

---

## 함수 (모두 `from core import ...`)

| 함수 | 파이프라인 단계 | 반환 |
| --- | --- | --- |
| `select_best_match(candidates)` | 리랭커 직후 — 최고 후보 선택(임계값 미적용) | `(StandardClause \| None, float)` |
| `classify_clause_deviation(matched_standard, score, match_threshold)` | 조항 단위 루프 — EXTRA / NONE 판정 | `Deviation` |
| `detect_missing_clauses(all_standard, matched_ids)` | 루프 종료 후 1회 — 한 번도 매칭 안 된 표준조항 수집 | `List[StandardClause]` |
| `traverse_related_risks(adjacency_list, clause_id, max_depth)` | 표준조항 기준 연관 조항 DFS 탐색 (고도화 A) | `List[str]` clause_id |
| `detect_toxic_patterns(matches, threshold)` | 조항 단위 루프 — 독소 패턴 역방향 검색 필터 (고도화 B) | `List[ToxicPattern]` |

---

## Deviation 분류 체계와 함수 대응

각 Deviation 값이 어느 함수에서 결정되는지, 주어가 무엇인지 정리합니다.

| Deviation | 주어 | 결정 위치 | 의미 |
| --- | --- | --- | --- |
| `EXTRA` | 사용자 조항 | `classify_clause_deviation` | 최고 후보가 있으나 점수가 임계값 미달인 비표준 검토 후보. 후보가 있으면 함께 반환한다. |
| `NONE` | 사용자 조항 | `classify_clause_deviation` | 점수가 임계값 이상인 **1차 잠정 매칭**. 본문 의미 동치의 최종 확정은 하지 않는다. |
| `MISSING` | **표준조항** | `detect_missing_clauses` | 표준에는 있는데 사용자 계약서에 대응 조항이 없음 |
| `NO_MATCH` | — | **pipe 레이어** | 검색 자체가 후보를 반환하지 못함 (core 밖) |

> `MISSING`의 주어가 사용자 조항이 아니라 표준조항이기 때문에, 단일 조항 루프 안에서 판단할 수 없어 `detect_missing_clauses`로 분리됩니다.
>
> `NO_MATCH`는 검색 결과가 비어 있음을 나타내는 명시 표식이므로 core가 아닌 pipe에서 직접 처리합니다. `classify_clause_deviation`에 후보 없음(`matched_standard=None`)이 들어오는 경우는 `EXTRA`가 올바릅니다.

---

## 임계치(Threshold) 가이드

현재 1차 판정 임계치는 하나이며, 초기값은 eval 결과를 근거로 유지·검토합니다.

| 파라미터 | 기본값 | 역할 |
| --- | --- | --- |
| `match_threshold` | 0.5 (pipe 주입) | 대응 표준조항으로 잠정 매칭할 최소 리랭커 점수. 미달 → `EXTRA` |

1차는 본문 글자 비교·항↔항 coverage 2-pass·치명변경 정규식 규칙을 사용하지 않습니다. 이 방식들은 의미 동치성을 안정적으로 판정하지 못해 폐기되었습니다. `NONE`과 근접후보가 있는 `EXTRA`의 실제 의미 차이는 서버 밖 2차 LLM이 원문과 `matched_standard`를 비교해 설명하는 책임입니다. 1차 표면 결과는 항상 표준 대비 **검토 후보**이며 법적 결론이 아닙니다.

> 과거의 `CHANGED`, `change_threshold`, 항↔항 정렬·coverage 2-pass 설계는 [J 재설계 카드](../../docs/tasks/J_deviation_redesign.md)의 폐기 이력에서만 참조합니다. 현재 런타임 계약이 아닙니다.

---

## 규칙
- adapter·config import 금지. 외부 데이터는 **인자로 주입**.
- 출력은 `contracts` 모델/enum으로. 빈 결과도 `NO_MATCH` 등 명시 표식.
- **1차에는 LLM·해석 생성 금지.** 검색·비교·분류·규칙만. (AGENTS.md 규칙 #1)
- 새 로직은 `tests/core/`에 테스트부터 작성(또는 통과)하고 구현.
