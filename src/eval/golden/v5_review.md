# v5 — 이탈 평가 기준선 리뷰

> 대상: `v5_si_subcontract.json` · `v5_sm_subcontract.json` · `v5_sw_freelance.json` 135건
>
> 실행: 2026-07-12 21:55:34 · `APP_ENV=prod` · 결과: `v5_result.md` · 진단: `v5_diagnostics.json`
>
> 본 문서의 수치는 표준 대비 이탈 및 독소 **검토 후보** 탐지의 결정론적 평가 결과다. 법적 위법성·유불리 판단 또는 프로덕션 임계값 자동 변경 근거가 아니다.

## 1. 기준선 유효성

- 계약유형별 45건, 전체 135건이다. 각 유형의 tuning 30건과 held-out 15건 모두 `EXTRA`와 `NONE`을 함께 포함한다.
- 유형별로 tuning은 `EXTRA` 20건·`NONE` 10건, held-out은 `EXTRA` 10건·`NONE` 5건으로 구성된다. 따라서 v4와 달리 SI·SM·SW 이탈 P/R/F1을 모두 비교할 수 있다.
- `python -m eval.golden.validate_golden v5`가 135건의 스키마, case matrix, split, held-out manifest 검증을 통과했다.
- case-level 진단의 이탈 135건과 독소 135건을 대조했다. 최종 `matched_standard`가 top-3 후보 또는 서브청크 부모에 없는 사례는 0건이다.
- v5 held-out은 이후 이탈 개선안의 독립 검증용으로 동결한다. v4는 독소 hard-negative challenge 용도로 계속 별도 유지한다.

## 2. 기준 설정

프로덕션 기본값은 유지한다.

| 항목 | 유지값 | 근거 |
| --- | ---: | --- |
| `match_threshold` | 0.50 | v5에서 0.55가 더 높은 F1을 보이지만, 동일 v5 결과만으로 채택하지 않는다. 별도 변경안·독립 검증·사람 사인오프가 필요하다. |
| `toxic_threshold` | 0.60 | v5는 독소 임계값 채택용 데이터셋이 아니며, v4의 동결된 hard-negative challenge 기준을 대체하지 않는다. |

## 3. 이탈 기준선 결과 (`match_threshold=0.50`)

| 계약유형 | P | R | F1 | TP | FP | FN | TN | 주된 오류 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| SI_SUBCONTRACT | 0.700 | 0.933 | 0.800 | 28 | 12 | 2 | 3 | `UNDER_MATCH` FP 12건 |
| SM_SUBCONTRACT | 0.735 | 0.833 | 0.781 | 25 | 9 | 5 | 6 | `UNDER_MATCH` FP 9건, `OVER_MATCH` FN 5건 |
| SW_FREELANCE | 0.842 | 0.533 | 0.653 | 16 | 3 | 14 | 12 | `OVER_MATCH` FN 14건 |
| 전체 | 0.742 | 0.767 | 0.754 | 69 | 24 | 21 | 21 | 유형별 실패 방향이 다름 |

SI와 SM은 표준 대응 `NONE`을 낮은 점수로 판단하는 under-match가 우세하다. 반대로 SW는 표준에 없는 `EXTRA`를 높은 점수로 매칭하는 over-match가 주된 실패다. 하나의 전역 임계값 조정으로 두 방향을 동시에 해결할 근거는 없다.

held-out 전체에서 0.55의 F1은 0.762로 0.50의 0.742보다 높고, tuning도 각각 0.770과 0.760이다. 그러나 이 값은 v5 설계·평가 후 관찰한 후보일 뿐 사전 선택된 변경안이 아니다. 현재 기본값은 0.50으로 유지하며, 후속 개선은 먼저 오류 메커니즘을 하나로 제한한 뒤 동결 held-out에서 검증한다.

## 4. 검색 및 독소 관찰

- 검색 ablation은 `dense`와 `hybrid_7_3`에서 Recall@5 1.000을 기록했다. 반면 모든 hybrid+rereanker 변형은 Recall@5 0.933으로 낮았다. v5의 검색 정답 집계는 `gold_clause_id`가 있는 45건만 대상으로 하므로, 이 수치만으로 `EXTRA` 분류 품질을 설명할 수는 없다.
- 독소 기본값 0.60의 유형별 F1은 SI 0.750, SM 0.462, SW 0.667이다. SM의 FN 7건 중 `SEARCH_MISS` 3건과 `BELOW_THRESHOLD` 4건이 남아 있으며, SW에는 `WRONG_PATTERN` FP 7건이 있다.
- 이 독소 관찰은 [실험 S](../../../docs/tasks/S_toxic_experiment.md)의 승인된 단일 가설을 검증할 때 참고하되, v5 결과로 패턴 데이터·임계값·MCP 계약을 변경하지 않는다.

## 5. 확정 결론과 다음 단계

1. v5를 유형별 이탈 성능 비교 및 후속 변경안의 독립 held-out 검증 기준선으로 채택한다.
2. `match_threshold=0.50`, `toxic_threshold=0.60`은 유지한다.
3. 다음 구현은 v5의 SW `OVER_MATCH` 또는 SI/SM `UNDER_MATCH` 중 **한 오류 메커니즘만** 대상으로 한 별도 실험 카드와 사람 사인오프 후 시작한다.
4. 독소 개선은 v5가 아니라 동결된 v4 hard-negative challenge 절차를 따른다. 실험 S 승인 전에는 구현하지 않는다.

## 6. 검증 기록

```text
python -m eval.golden.validate_golden v5
OK — v5 골든셋(135건) 스키마 검증 통과, 위반 없음.

pytest tests/eval/test_validate_golden.py tests/eval/test_run_eval.py tests/eval/test_diagnostics.py
47 passed
```
