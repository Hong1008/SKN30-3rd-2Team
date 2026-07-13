# C — 후보 출처 비교

> tuning OVER_MATCH만 사용합니다. `없음`은 top-3에서 해당 출처를 관측하지 못했다는 뜻이며 점수 0을 뜻하지 않습니다.

| case_id | outcome | OVER_MATCH | 표준 조항(score) | 서브청크 부모(score) | 부모 일치 | 승자 | 점수 차 |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| v5-sw-01 | FN | 예 | 없음 | sw_freelance-2020-art4 (0.976321) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-04 | FN | 예 | sw_freelance-2020-art20 (0.027692) | sw_freelance-2020-art20 (0.999091) | 일치 | SUB_CHUNK | 0.971399 |
| v5-sw-05 | FN | 예 | sw_freelance-2020-art20 (0.000074) | sw_freelance-2020-art20 (0.853941) | 일치 | SUB_CHUNK | 0.853866 |
| v5-sw-07 | FN | 예 | sw_freelance-2020-art6 (0.891280) | sw_freelance-2020-art16 (0.175820) | 불일치 | STANDARD_CLAUSE | 0.715461 |
| v5-sw-10 | FN | 예 | sw_freelance-2020-art16 (0.996003) | sw_freelance-2020-art16 (0.994810) | 일치 | STANDARD_CLAUSE | 0.001193 |
| v5-sw-11 | FN | 예 | 없음 | sw_freelance-2020-art16 (0.995991) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-13 | FN | 예 | sw_freelance-2020-art17 (0.950737) | sw_freelance-2020-art17 (0.014257) | 일치 | STANDARD_CLAUSE | 0.936480 |
| v5-sw-19 | FN | 예 | sw_freelance-2020-art21 (0.679969) | sw_freelance-2020-art21 (0.679970) | 일치 | SUB_CHUNK | 0.000002 |
| v5-sw-22 | FN | 예 | sw_freelance-2020-art15 (0.999997) | sw_freelance-2020-art15 (0.999997) | 일치 | STANDARD_CLAUSE | 0.000000 |
| v5-sw-28 | FN | 예 | sw_freelance-2020-art11 (0.021323) | sw_freelance-2020-art10 (0.546096) | 불일치 | SUB_CHUNK | 0.524773 |
