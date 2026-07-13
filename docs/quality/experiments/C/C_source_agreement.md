# C — tuning 전체 후보 출처 비교

> tuning 전체만 사용합니다. held-out은 읽지 않습니다. `없음`은 top-3에서 해당 출처를 관측하지 못했다는 뜻이며 점수 0을 뜻하지 않습니다.

| case_id | outcome | OVER_MATCH | 표준 조항(score) | 서브청크 부모(score) | 부모 일치 | 승자 | 점수 차 |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| v5-sw-01 | FN | 예 | 없음 | sw_freelance-2020-art4 (0.976321) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-02 | TP | 아니오 | 없음 | sw_freelance-2020-art10 (0.023819) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-03 | FP | 아니오 | 없음 | sw_freelance-2020-art14 (0.367849) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-04 | FN | 예 | sw_freelance-2020-art20 (0.027692) | sw_freelance-2020-art20 (0.999091) | 일치 | SUB_CHUNK | 0.971399 |
| v5-sw-05 | FN | 예 | sw_freelance-2020-art20 (0.000074) | sw_freelance-2020-art20 (0.853941) | 일치 | SUB_CHUNK | 0.853866 |
| v5-sw-06 | TN | 아니오 | sw_freelance-2020-art20 (0.003892) | sw_freelance-2020-art20 (0.999989) | 일치 | SUB_CHUNK | 0.996097 |
| v5-sw-07 | FN | 예 | sw_freelance-2020-art6 (0.891280) | sw_freelance-2020-art16 (0.175820) | 불일치 | STANDARD_CLAUSE | 0.715461 |
| v5-sw-08 | TP | 아니오 | sw_freelance-2020-art6 (0.000002) | sw_freelance-2020-art10 (0.000396) | 불일치 | SUB_CHUNK | 0.000394 |
| v5-sw-09 | TN | 아니오 | sw_freelance-2020-art6 (0.994291) | sw_freelance-2020-art6 (0.865219) | 일치 | STANDARD_CLAUSE | 0.129072 |
| v5-sw-10 | FN | 예 | sw_freelance-2020-art16 (0.996003) | sw_freelance-2020-art16 (0.994810) | 일치 | STANDARD_CLAUSE | 0.001193 |
| v5-sw-11 | FN | 예 | 없음 | sw_freelance-2020-art16 (0.995991) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-12 | TN | 아니오 | sw_freelance-2020-art16 (0.999524) | sw_freelance-2020-art16 (0.999980) | 일치 | SUB_CHUNK | 0.000456 |
| v5-sw-13 | FN | 예 | sw_freelance-2020-art17 (0.950737) | sw_freelance-2020-art17 (0.014257) | 일치 | STANDARD_CLAUSE | 0.936480 |
| v5-sw-14 | TP | 아니오 | 없음 | sw_freelance-2020-art17 (0.017714) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-15 | FP | 아니오 | sw_freelance-2020-art17 (0.242668) | sw_freelance-2020-art17 (0.244676) | 일치 | SUB_CHUNK | 0.002008 |
| v5-sw-16 | TP | 아니오 | 없음 | sw_freelance-2020-art16 (0.000091) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-17 | TP | 아니오 | 없음 | sw_freelance-2020-art19 (0.000022) | 미관측 | SUB_CHUNK | 미관측 |
| v5-sw-18 | TN | 아니오 | sw_freelance-2020-art18 (0.933207) | sw_freelance-2020-art18 (0.933207) | 일치 | SUB_CHUNK | 0.000000 |
| v5-sw-19 | FN | 예 | sw_freelance-2020-art21 (0.679969) | sw_freelance-2020-art21 (0.679970) | 일치 | SUB_CHUNK | 0.000002 |
| v5-sw-20 | TP | 아니오 | sw_freelance-2020-art21 (0.005162) | sw_freelance-2020-art21 (0.005162) | 일치 | SUB_CHUNK | 0.000000 |
| v5-sw-21 | TN | 아니오 | sw_freelance-2020-art21 (0.999994) | sw_freelance-2020-art21 (0.999994) | 일치 | STANDARD_CLAUSE | 0.000000 |
| v5-sw-22 | FN | 예 | sw_freelance-2020-art15 (0.999997) | sw_freelance-2020-art15 (0.999997) | 일치 | STANDARD_CLAUSE | 0.000000 |
| v5-sw-23 | TP | 아니오 | sw_freelance-2020-art15 (0.036073) | sw_freelance-2020-art15 (0.036073) | 일치 | STANDARD_CLAUSE | 0.000000 |
| v5-sw-24 | TN | 아니오 | sw_freelance-2020-art15 (0.999997) | sw_freelance-2020-art15 (0.999997) | 일치 | STANDARD_CLAUSE | 0.000000 |
| v5-sw-25 | TP | 아니오 | sw_freelance-2020-art12 (0.006402) | sw_freelance-2020-art12 (0.038164) | 일치 | SUB_CHUNK | 0.031762 |
| v5-sw-26 | TP | 아니오 | sw_freelance-2020-art12 (0.000005) | sw_freelance-2020-art12 (0.018721) | 일치 | SUB_CHUNK | 0.018716 |
| v5-sw-27 | TN | 아니오 | sw_freelance-2020-art12 (0.999992) | sw_freelance-2020-art12 (0.999952) | 일치 | STANDARD_CLAUSE | 0.000040 |
| v5-sw-28 | FN | 예 | sw_freelance-2020-art11 (0.021323) | sw_freelance-2020-art10 (0.546096) | 불일치 | SUB_CHUNK | 0.524773 |
| v5-sw-29 | TP | 아니오 | sw_freelance-2020-art11 (0.001722) | sw_freelance-2020-art11 (0.001722) | 일치 | SUB_CHUNK | 0.000000 |
| v5-sw-30 | TN | 아니오 | sw_freelance-2020-art11 (0.999984) | sw_freelance-2020-art11 (0.999984) | 일치 | STANDARD_CLAUSE | 0.000000 |
