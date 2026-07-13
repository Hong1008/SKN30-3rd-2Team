# C — SW OVER_MATCH taxonomy

> v5 SW tuning 30건에서만 작성한 고정 진단입니다. `EXTRA`를 `NONE`으로 예측한 10건만 포함합니다.

정의: `gold_deviation=EXTRA`이고 `predicted_deviation=NONE`

## 축별 집계

| 축 | 관찰값 | 건수 |
| --- | --- | ---: |
| 후보 출처 | `standard_sub_chunks` | 6 |
| 후보 출처 | `standard_clauses` | 4 |
| trap | `paraphrase` | 2 |
| trap | `number` | 2 |
| trap | `negation` | 2 |
| trap | `contradiction` | 2 |
| trap | `reorder` | 1 |
| trap | `party` | 1 |
| contrast_clause_id | `sw_freelance-2020-art20` | 2 |
| contrast_clause_id | `sw_freelance-2020-art16` | 2 |
| contrast_clause_id | 기타 6개 조항 | 6 |

## 사례별 관찰값

| case_id | contrast_clause_id | top1-top2 gap | trap | source |
| --- | --- | ---: | --- | --- |
| v5-sw-01 | sw_freelance-2020-art4 | 0.858572 | paraphrase | standard_sub_chunks |
| v5-sw-04 | sw_freelance-2020-art20 | 0.889605 | paraphrase | standard_clauses |
| v5-sw-05 | sw_freelance-2020-art20 | 0.853788 | number | standard_sub_chunks |
| v5-sw-07 | sw_freelance-2020-art6 | 0.715461 | number | standard_clauses |
| v5-sw-10 | sw_freelance-2020-art16 | 0.001193 | negation | standard_sub_chunks |
| v5-sw-11 | sw_freelance-2020-art16 | 0.995954 | contradiction | standard_clauses |
| v5-sw-13 | sw_freelance-2020-art17 | 0.936480 | negation | standard_sub_chunks |
| v5-sw-19 | sw_freelance-2020-art21 | 0.000002 | contradiction | standard_sub_chunks |
| v5-sw-22 | sw_freelance-2020-art15 | 0.000000 | party | standard_sub_chunks |
| v5-sw-28 | sw_freelance-2020-art11 | 0.518057 | reorder | standard_clauses |

이 표는 원인 해석이나 변경 승인 자체가 아니다. 반복 원인 하나의 선택, 변경 레이어, 예상 실패
양상과 기준은 사람 승인 파일에 기록한 뒤에만 구현 단계로 이동한다.
