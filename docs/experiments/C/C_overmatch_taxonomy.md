# C — SW OVER_MATCH taxonomy

> tuning의 OVER_MATCH만 기록합니다. held-out 진단은 이 문서 작성에 사용하지 않습니다.

- 표본 수: 10
- 정의: `gold_deviation=EXTRA`이고 `predicted_deviation=NONE`

## contrast_clause_id

| 값 | 건수 |
| --- | ---: |
| sw_freelance-2020-art16 | 2 |
| sw_freelance-2020-art20 | 2 |
| sw_freelance-2020-art11 | 1 |
| sw_freelance-2020-art15 | 1 |
| sw_freelance-2020-art17 | 1 |
| sw_freelance-2020-art21 | 1 |
| sw_freelance-2020-art4 | 1 |
| sw_freelance-2020-art6 | 1 |

## trap

| 값 | 건수 |
| --- | ---: |
| contradiction | 2 |
| negation | 2 |
| number | 2 |
| paraphrase | 2 |
| party | 1 |
| reorder | 1 |

## candidate_source

| 값 | 건수 |
| --- | ---: |
| standard_sub_chunks | 6 |
| standard_clauses | 4 |

## candidate_parent_clause_id

| 값 | 건수 |
| --- | ---: |
| None | 4 |
| sw_freelance-2020-art20 | 2 |
| sw_freelance-2020-art10 | 1 |
| sw_freelance-2020-art16 | 1 |
| sw_freelance-2020-art21 | 1 |
| sw_freelance-2020-art4 | 1 |

## topic_group

| 값 | 건수 |
| --- | ---: |
| v5-sw-t02 | 2 |
| v5-sw-t04 | 2 |
| v5-sw-t01 | 1 |
| v5-sw-t03 | 1 |
| v5-sw-t05 | 1 |
| v5-sw-t07 | 1 |
| v5-sw-t08 | 1 |
| v5-sw-t10 | 1 |

## 사례

| case_id | contrast | top1-top2 gap | trap | source |
| --- | --- | ---: | --- | --- |
| v5-sw-01 | sw_freelance-2020-art4 | 0.858572 | paraphrase | standard_sub_chunks |
| v5-sw-04 | sw_freelance-2020-art20 | 0.889605 | number | standard_sub_chunks |
| v5-sw-05 | sw_freelance-2020-art20 | 0.853788 | negation | standard_sub_chunks |
| v5-sw-07 | sw_freelance-2020-art6 | 0.715461 | contradiction | standard_clauses |
| v5-sw-10 | sw_freelance-2020-art16 | 0.001193 | reorder | standard_clauses |
| v5-sw-11 | sw_freelance-2020-art16 | 0.995954 | number | standard_sub_chunks |
| v5-sw-13 | sw_freelance-2020-art17 | 0.936480 | party | standard_clauses |
| v5-sw-19 | sw_freelance-2020-art21 | 0.000002 | negation | standard_sub_chunks |
| v5-sw-22 | sw_freelance-2020-art15 | 0.000000 | paraphrase | standard_clauses |
| v5-sw-28 | sw_freelance-2020-art11 | 0.518057 | contradiction | standard_sub_chunks |
