# 독소 오류 원인 분류표

## 1. 목적과 범위

v3/v4 독소 진단의 FP/FN을 후보 탐색·점수·과매칭 관점에서 재현 가능하게 분류한다. 이 문서는 평가 진단용이며 코퍼스, 임계값, 런타임 판정 코드를 변경하지 않는다.

분석 입력은 다음 파일이다.

- `src/eval/golden/v3_diagnostics.json`
- `src/eval/golden/v4_diagnostics.json`

의미 차원의 확인을 위해 사례 원문과 `trap`/`note`만 골든 JSON에서 읽기 전용으로 대조했다. 독소성에 대한 법적 판단은 하지 않는다.

## 2. 기준선

| 버전 | FP | FN | 오류 합계 | toxic 레코드 |
| --- | ---: | ---: | ---: | ---: |
| v3 | 31 | 10 | 41 | 117 |
| v4 | 5 | 16 | 21 | 54 |
| 합계 | 36 | 26 | 62 | 171 |

두 진단 파일의 toxic 오류 62건 모두 `case_id`, 계약 유형, gold/predicted pattern, top-3 후보·점수, threshold, outcome, 기존 reason을 보존한다.

- 독소 판정 임계값: `toxic_threshold=0.60` (v3/v4 공통)

## 3. 분류 규칙

### 3.1 `primary_reason`

각 오류에 정확히 하나의 주 원인을 부여한다.

| 표식 | 결정론적 기준 |
| --- | --- |
| `SEARCH_MISS` | `top_candidates`가 비어 있거나 진단에 후보 없음 표식이 명시된 경우. 이 문서에서의 검색 실패는 저장된 진단 근거에 한정한다. |
| `LOW_SCORE` | FN이며 후보가 하나 이상 있으나 정답 패턴이 임계값 이상으로 검출되지 않은 경우. |
| `OVER_MATCH` | FP인 경우. 정상 hard-negative가 독소 패턴으로 검출된 운영 결과를 나타낸다. |
| `UNMAPPED_PATTERN` | 원문과 현재 `ToxicPattern` 전체를 대조해 기존 패턴에 대응하지 않는 새로운 검토 패턴 후보임을 확인한 경우에만 사용한다. |

현재 v3/v4 오류에는 빈 `top_candidates`가 없으므로 `SEARCH_MISS`는 0건이다. top-3에 gold 패턴이 없더라도 후보가 존재하는 FN은 `SEARCH_MISS`로 확대하지 않고 `LOW_SCORE`로 분류한다. 이는 저장된 top-3만으로 검색 전체 실패를 주장하지 않기 위한 제한이다.

### 3.2 `semantic_dimension`

의미 차이는 주 원인과 분리한다. 값은 `none`, `negation`, `period`, `numeric`, `authority_subject`, `unmapped` 중 하나다.

- `negation`: 부정 또는 의미 반전. 골든의 `contradiction`도 이 차원으로 통합한다.
- `period`: 기간·기한의 존재, 범위 또는 종료 시점 차이.
- `numeric`: 금액, 비율, 일수, 상한 등 수치 차이.
- `authority_subject`: 행위·책임·권한 주체가 달라진 경우.
- `unmapped`: 새 검토 패턴 후보로 확인된 경우.
- `none`: 위 차원이 확인되지 않은 경우.

따라서 FP는 항상 `OVER_MATCH`이고, 의미 차원이 있으면 별도 필드로 기록한다. 의미 차원과 `primary_reason`을 혼용하지 않는다.

### 3.3 확신도

- `CONFIRMED`: 사용자 원문, gold JSON, 독소 패턴 원문을 모두 대조해 규칙에 직접 부합한다.
- `INFERRED`: 진단의 후보·점수·기존 reason 또는 골든의 `trap`/`note`에서 운영 원인을 추정한다.

이번 문서의 primary 분류는 진단 파일의 후보·점수 규칙으로 재현되지만, 독소 패턴 원문까지 대조한 감사 기록은 아니므로 사례의 `confidence`는 `INFERRED`로 고정한다. 의미 차원은 골든의 `trap`을 다음처럼 보조 매핑했다: `negation`/`contradiction` → `negation`, `party` → `authority_subject`, `number` → `numeric`.

## 4. 집계표

### 4.1 primary_reason별

| 버전 | SEARCH_MISS | LOW_SCORE | OVER_MATCH | UNMAPPED_PATTERN | 합계 |
| --- | ---: | ---: | ---: | ---: | ---: |
| v3 | 0 | 10 | 31 | 0 | 41 |
| v4 | 0 | 16 | 5 | 0 | 21 |
| 합계 | 0 | 26 | 36 | 0 | 62 |

### 4.2 계약 유형별

| 버전 | 계약 유형 | FP / OVER_MATCH | FN / LOW_SCORE | 합계 |
| --- | --- | ---: | ---: | ---: |
| v3 | SI_SUBCONTRACT | 14 | 4 | 18 |
| v3 | SM_SUBCONTRACT | 7 | 5 | 12 |
| v3 | SW_FREELANCE | 10 | 1 | 11 |
| v4 | SI_SUBCONTRACT | 2 | 5 | 7 |
| v4 | SM_SUBCONTRACT | 1 | 9 | 10 |
| v4 | SW_FREELANCE | 1 | 3 | 4 |

### 4.3 semantic_dimension별

| 버전 | none | negation | numeric | authority_subject | period | unmapped | 합계 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v3 | 36 | 3 | 1 | 1 | 0 | 0 | 41 |
| v4 | 5 | 9 | 0 | 7 | 0 | 0 | 21 |
| 합계 | 41 | 12 | 1 | 8 | 0 | 0 | 62 |

### 4.4 패턴별 오류 사례 수

FP는 여러 predicted pattern이 함께 기록될 수 있으므로, 아래 표는 사례별 gold pattern(FN) 또는 predicted pattern(FP)의 **패턴 언급 횟수**다. 따라서 사례 합계와 일대일로 비교하지 않는다.

| 패턴 | v3 | v4 | 합계 |
| --- | ---: | ---: | ---: |
| `IP_TOTAL_FREE` | 9 | 4 | 13 |
| `UNILATERAL_INTERPRETATION` | 8 | 2 | 10 |
| `UNPAID_ADDITIONAL_WORK` | 11 | 4 | 15 |
| `UNILATERAL_CHANGE` | 7 | 2 | 9 |
| `NONCOMPETE_EXCESS` | 4 | 1 | 5 |
| `PAYMENT_DELAY_UNFAIR` | 7 | 0 | 7 |
| `INDEFINITE_CONFIDENTIALITY` | 7 | 2 | 9 |
| `UNFAIR_DAMAGE_CLAIM` | 7 | 4 | 11 |
| `UNILATERAL_CANCELLATION` | 3 | 3 | 6 |

## 5. 전체 사례 목록

표의 `semantic_dimension`은 원인 표식이 아니라 의미 차원이다. `confidence=INFERRED`는 원문·패턴 정의 전체를 사용한 확정 감사가 아니라는 뜻이다.

| case_id | contract_type | outcome | primary_reason | semantic_dimension | confidence |
| --- | --- | --- | --- | --- | --- |
| v3-si-01 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-02 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-12 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-13 | SI_SUBCONTRACT | FP | OVER_MATCH | negation | INFERRED |
| v3-si-14 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-15 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-16 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-17 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-29 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-31 | SI_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-si-32 | SI_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-si-33 | SI_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-si-34 | SI_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-si-36 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-41 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-42 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-44 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-si-45 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sm-01 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sm-02 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sm-16 | SM_SUBCONTRACT | FP | OVER_MATCH | negation | INFERRED |
| v3-sm-17 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sm-21 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sm-31 | SM_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-sm-32 | SM_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-sm-33 | SM_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-sm-34 | SM_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-sm-35 | SM_SUBCONTRACT | FN | LOW_SCORE | none | INFERRED |
| v3-sm-41 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sm-44 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v3-sw-01 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v3-sw-06 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v3-sw-08 | SW_FREELANCE | FP | OVER_MATCH | negation | INFERRED |
| v3-sw-09 | SW_FREELANCE | FP | OVER_MATCH | authority_subject | INFERRED |
| v3-sw-10 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v3-sw-13 | SW_FREELANCE | FP | OVER_MATCH | numeric | INFERRED |
| v3-sw-15 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v3-sw-17 | SW_FREELANCE | FN | LOW_SCORE | none | INFERRED |
| v3-sw-21 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v3-sw-23 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v3-sw-25 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v4-si-03 | SI_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-si-08 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v4-si-09 | SI_SUBCONTRACT | FN | LOW_SCORE | negation | INFERRED |
| v4-si-11 | SI_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-si-12 | SI_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v4-si-13 | SI_SUBCONTRACT | FN | LOW_SCORE | negation | INFERRED |
| v4-si-15 | SI_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-sm-01 | SM_SUBCONTRACT | FN | LOW_SCORE | negation | INFERRED |
| v4-sm-03 | SM_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-sm-05 | SM_SUBCONTRACT | FN | LOW_SCORE | negation | INFERRED |
| v4-sm-06 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v4-sm-07 | SM_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-sm-11 | SM_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-sm-12 | SM_SUBCONTRACT | FP | OVER_MATCH | none | INFERRED |
| v4-sm-13 | SM_SUBCONTRACT | FN | LOW_SCORE | negation | INFERRED |
| v4-sm-15 | SM_SUBCONTRACT | FN | LOW_SCORE | authority_subject | INFERRED |
| v4-sm-17 | SM_SUBCONTRACT | FN | LOW_SCORE | negation | INFERRED |
| v4-sw-01 | SW_FREELANCE | FN | LOW_SCORE | negation | INFERRED |
| v4-sw-04 | SW_FREELANCE | FP | OVER_MATCH | none | INFERRED |
| v4-sw-13 | SW_FREELANCE | FN | LOW_SCORE | negation | INFERRED |
| v4-sw-17 | SW_FREELANCE | FN | LOW_SCORE | negation | INFERRED |

### 5.1 사례별 증거 상세

아래 표는 위 사례 목록의 재검증용 원자료를 압축한 것이다. top-3는 `pattern:score` 형식이며 점수는 원본 JSON을 소수점 넷째 자리까지 표시했다.

| case_id | outcome | gold → predicted | top-3 후보(점수) | threshold | primary_reason | semantic_dimension | evidence | confidence |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| v3-si-01 | FP | ∅ → IP_TOTAL_FREE, UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.9996; IP_TOTAL_FREE:0.9948; IP_TOTAL_FREE:0.9721 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-02 | FP | ∅ → IP_TOTAL_FREE, UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.9829; UNILATERAL_INTERPRETATION:0.9499; IP_TOTAL_FREE:0.7537 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-12 | FP | ∅ → UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.9864; UNPAID_ADDITIONAL_WORK:0.9845; UNPAID_ADDITIONAL_WORK:0.9203 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-13 | FP | ∅ → UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.9971; UNPAID_ADDITIONAL_WORK:0.9073; UNPAID_ADDITIONAL_WORK:0.1830 | 0.60 | OVER_MATCH | negation | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-14 | FP | ∅ → UNILATERAL_CHANGE, UNPAID_ADDITIONAL_WORK | UNILATERAL_CHANGE:0.9186; UNPAID_ADDITIONAL_WORK:0.9145; UNPAID_ADDITIONAL_WORK:0.8367 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-15 | FP | ∅ → NONCOMPETE_EXCESS, PAYMENT_DELAY_UNFAIR, UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.9998; NONCOMPETE_EXCESS:0.9997; PAYMENT_DELAY_UNFAIR:0.9996 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-16 | FP | ∅ → UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.6298; UNPAID_ADDITIONAL_WORK:0.4636; UNPAID_ADDITIONAL_WORK:0.3995 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-17 | FP | ∅ → NONCOMPETE_EXCESS, UNILATERAL_CHANGE | NONCOMPETE_EXCESS:0.7215; UNILATERAL_CHANGE:0.6152; IP_TOTAL_FREE:0.3248 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-29 | FP | ∅ → INDEFINITE_CONFIDENTIALITY, UNFAIR_DAMAGE_CLAIM | UNFAIR_DAMAGE_CLAIM:0.9745; INDEFINITE_CONFIDENTIALITY:0.8759; UNFAIR_DAMAGE_CLAIM:0.0035 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-31 | FN | NONCOMPETE_EXCESS → ∅ | NONCOMPETE_EXCESS:0.0005; NONCOMPETE_EXCESS:0.0002; NONCOMPETE_EXCESS:0.0001 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-si-32 | FN | UNPAID_ADDITIONAL_WORK → ∅ | UNFAIR_DAMAGE_CLAIM:0.0310; UNPAID_ADDITIONAL_WORK:0.0269; UNPAID_ADDITIONAL_WORK:0.0237 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-si-33 | FN | UNILATERAL_CHANGE, UNPAID_ADDITIONAL_WORK → ∅ | UNPAID_ADDITIONAL_WORK:0.0003; UNILATERAL_CHANGE:0.0002; UNPAID_ADDITIONAL_WORK:0.0002 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-si-34 | FN | PAYMENT_DELAY_UNFAIR, UNFAIR_DAMAGE_CLAIM → ∅ | PAYMENT_DELAY_UNFAIR:0.0014; PAYMENT_DELAY_UNFAIR:0.0002; UNFAIR_DAMAGE_CLAIM:0.0001 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-si-36 | FP | ∅ → IP_TOTAL_FREE, UNILATERAL_CHANGE | UNILATERAL_CHANGE:0.8402; IP_TOTAL_FREE:0.8025; IP_TOTAL_FREE:0.7500 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-41 | FP | ∅ → PAYMENT_DELAY_UNFAIR | PAYMENT_DELAY_UNFAIR:0.6182; PAYMENT_DELAY_UNFAIR:0.1846; PAYMENT_DELAY_UNFAIR:0.1356 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-42 | FP | ∅ → IP_TOTAL_FREE, NONCOMPETE_EXCESS | NONCOMPETE_EXCESS:0.9552; IP_TOTAL_FREE:0.8889; UNILATERAL_CHANGE:0.5877 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-44 | FP | ∅ → UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.9934; UNILATERAL_INTERPRETATION:0.9925; UNILATERAL_INTERPRETATION:0.9868 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-si-45 | FP | ∅ → PAYMENT_DELAY_UNFAIR, UNILATERAL_CHANGE, UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.9999; UNILATERAL_CHANGE:0.9999; PAYMENT_DELAY_UNFAIR:0.9998 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-01 | FP | ∅ → IP_TOTAL_FREE, UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.9997; IP_TOTAL_FREE:0.9992; IP_TOTAL_FREE:0.9987 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-02 | FP | ∅ → UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.8337; UNILATERAL_INTERPRETATION:0.7696; INDEFINITE_CONFIDENTIALITY:0.0063 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-16 | FP | ∅ → IP_TOTAL_FREE | IP_TOTAL_FREE:0.7446; IP_TOTAL_FREE:0.3164; IP_TOTAL_FREE:0.1787 | 0.60 | OVER_MATCH | negation | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-17 | FP | ∅ → INDEFINITE_CONFIDENTIALITY, IP_TOTAL_FREE, UNILATERAL_CANCELLATION | IP_TOTAL_FREE:0.8892; UNILATERAL_CANCELLATION:0.8360; INDEFINITE_CONFIDENTIALITY:0.8174 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-21 | FP | ∅ → UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.7414; UNPAID_ADDITIONAL_WORK:0.6229; UNPAID_ADDITIONAL_WORK:0.5637 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-31 | FN | INDEFINITE_CONFIDENTIALITY → ∅ | INDEFINITE_CONFIDENTIALITY:0.0237; INDEFINITE_CONFIDENTIALITY:0.0122; INDEFINITE_CONFIDENTIALITY:0.0008 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-sm-32 | FN | UNPAID_ADDITIONAL_WORK → ∅ | UNPAID_ADDITIONAL_WORK:0.0035; UNPAID_ADDITIONAL_WORK:0.0009; UNPAID_ADDITIONAL_WORK:0.0001 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-sm-33 | FN | UNFAIR_DAMAGE_CLAIM, UNILATERAL_CHANGE → ∅ | NONCOMPETE_EXCESS:0.0088; NONCOMPETE_EXCESS:0.0084; UNFAIR_DAMAGE_CLAIM:0.0040 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-sm-34 | FN | UNFAIR_DAMAGE_CLAIM → ∅ | INDEFINITE_CONFIDENTIALITY:0.0051; UNFAIR_DAMAGE_CLAIM:0.0003; UNFAIR_DAMAGE_CLAIM:0.0000 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-sm-35 | FN | UNILATERAL_INTERPRETATION → ∅ | UNILATERAL_INTERPRETATION:0.0025; UNILATERAL_INTERPRETATION:0.0002; INDEFINITE_CONFIDENTIALITY:0.0000 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-sm-41 | FP | ∅ → PAYMENT_DELAY_UNFAIR | PAYMENT_DELAY_UNFAIR:0.6428; UNILATERAL_CHANGE:0.4808; PAYMENT_DELAY_UNFAIR:0.0200 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sm-44 | FP | ∅ → UNFAIR_DAMAGE_CLAIM, UNILATERAL_CANCELLATION, UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.9570; UNILATERAL_CANCELLATION:0.7162; UNFAIR_DAMAGE_CLAIM:0.6459 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-01 | FP | ∅ → IP_TOTAL_FREE, UNPAID_ADDITIONAL_WORK | UNPAID_ADDITIONAL_WORK:0.9995; IP_TOTAL_FREE:0.9994; UNPAID_ADDITIONAL_WORK:0.8949 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-06 | FP | ∅ → INDEFINITE_CONFIDENTIALITY | INDEFINITE_CONFIDENTIALITY:0.9911; INDEFINITE_CONFIDENTIALITY:0.9810; INDEFINITE_CONFIDENTIALITY:0.9343 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-08 | FP | ∅ → INDEFINITE_CONFIDENTIALITY | INDEFINITE_CONFIDENTIALITY:0.9969; INDEFINITE_CONFIDENTIALITY:0.9802; INDEFINITE_CONFIDENTIALITY:0.9506 | 0.60 | OVER_MATCH | negation | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-09 | FP | ∅ → INDEFINITE_CONFIDENTIALITY | INDEFINITE_CONFIDENTIALITY:0.9693; INDEFINITE_CONFIDENTIALITY:0.9211; INDEFINITE_CONFIDENTIALITY:0.5774 | 0.60 | OVER_MATCH | authority_subject | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-10 | FP | ∅ → IP_TOTAL_FREE | IP_TOTAL_FREE:0.9910; IP_TOTAL_FREE:0.9891; IP_TOTAL_FREE:0.9333 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-13 | FP | ∅ → PAYMENT_DELAY_UNFAIR | PAYMENT_DELAY_UNFAIR:0.8314; PAYMENT_DELAY_UNFAIR:0.4377; PAYMENT_DELAY_UNFAIR:0.3923 | 0.60 | OVER_MATCH | numeric | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-15 | FP | ∅ → PAYMENT_DELAY_UNFAIR, UNFAIR_DAMAGE_CLAIM | PAYMENT_DELAY_UNFAIR:0.6497; UNFAIR_DAMAGE_CLAIM:0.6491; UNFAIR_DAMAGE_CLAIM:0.6452 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-17 | FN | UNFAIR_DAMAGE_CLAIM → ∅ | UNFAIR_DAMAGE_CLAIM:0.0204; NONCOMPETE_EXCESS:0.0007; UNFAIR_DAMAGE_CLAIM:0.0000 | 0.60 | LOW_SCORE | none | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v3-sw-21 | FP | ∅ → UNILATERAL_CHANGE | UNILATERAL_CHANGE:0.7734; UNILATERAL_CHANGE:0.4580; PAYMENT_DELAY_UNFAIR:0.3056 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-23 | FP | ∅ → UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:1.0000; UNILATERAL_INTERPRETATION:1.0000; UNILATERAL_INTERPRETATION:0.9936 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v3-sw-25 | FP | ∅ → INDEFINITE_CONFIDENTIALITY, UNILATERAL_CANCELLATION | INDEFINITE_CONFIDENTIALITY:0.9962; UNILATERAL_CANCELLATION:0.9949; UNILATERAL_CANCELLATION:0.9754 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v4-si-03 | FN | IP_TOTAL_FREE → ∅ | IP_TOTAL_FREE:0.0424; IP_TOTAL_FREE:0.0306; IP_TOTAL_FREE:0.0012 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-si-08 | FP | ∅ → UNILATERAL_INTERPRETATION | UNILATERAL_INTERPRETATION:0.8743; UNILATERAL_INTERPRETATION:0.4395; UNILATERAL_INTERPRETATION:0.2059 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v4-si-09 | FN | UNFAIR_DAMAGE_CLAIM → ∅ | UNILATERAL_CHANGE:0.0747; NONCOMPETE_EXCESS:0.0222; UNFAIR_DAMAGE_CLAIM:0.0116 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-si-11 | FN | UNILATERAL_CHANGE → ∅ | UNILATERAL_CANCELLATION:0.0024; UNILATERAL_CHANGE:0.0018; UNILATERAL_CANCELLATION:0.0010 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-si-12 | FP | ∅ → UNILATERAL_CANCELLATION | UNILATERAL_CANCELLATION:0.6385; UNFAIR_DAMAGE_CLAIM:0.5729; UNILATERAL_CANCELLATION:0.4232 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v4-si-13 | FN | UNPAID_ADDITIONAL_WORK → ∅ | UNPAID_ADDITIONAL_WORK:0.0757; UNPAID_ADDITIONAL_WORK:0.0267; UNPAID_ADDITIONAL_WORK:0.0019 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-si-15 | FN | IP_TOTAL_FREE → ∅ | IP_TOTAL_FREE:0.0015; IP_TOTAL_FREE:0.0004; IP_TOTAL_FREE:0.0001 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-01 | FN | UNPAID_ADDITIONAL_WORK → ∅ | UNPAID_ADDITIONAL_WORK:0.0000; UNPAID_ADDITIONAL_WORK:0.0000; UNILATERAL_CHANGE:0.0000 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-03 | FN | IP_TOTAL_FREE → ∅ | IP_TOTAL_FREE:0.0022; IP_TOTAL_FREE:0.0006; IP_TOTAL_FREE:0.0002 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-05 | FN | INDEFINITE_CONFIDENTIALITY → ∅ | INDEFINITE_CONFIDENTIALITY:0.1913; INDEFINITE_CONFIDENTIALITY:0.0434; INDEFINITE_CONFIDENTIALITY:0.0193 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-06 | FP | ∅ → INDEFINITE_CONFIDENTIALITY | INDEFINITE_CONFIDENTIALITY:0.9913; INDEFINITE_CONFIDENTIALITY:0.9670; INDEFINITE_CONFIDENTIALITY:0.0658 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v4-sm-07 | FN | UNILATERAL_INTERPRETATION → ∅ | UNILATERAL_INTERPRETATION:0.0028; UNILATERAL_INTERPRETATION:0.0000; UNILATERAL_INTERPRETATION:0.0000 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-11 | FN | UNILATERAL_CANCELLATION → ∅ | UNILATERAL_CANCELLATION:0.2264; UNILATERAL_CANCELLATION:0.0341; UNILATERAL_CANCELLATION:0.0017 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-12 | FP | ∅ → UNFAIR_DAMAGE_CLAIM, UNILATERAL_CANCELLATION | UNILATERAL_CANCELLATION:0.9933; UNFAIR_DAMAGE_CLAIM:0.9844; UNILATERAL_CANCELLATION:0.6836 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v4-sm-13 | FN | NONCOMPETE_EXCESS → ∅ | NONCOMPETE_EXCESS:0.0292; NONCOMPETE_EXCESS:0.0045; UNFAIR_DAMAGE_CLAIM:0.0002 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-15 | FN | UNILATERAL_CHANGE → ∅ | UNILATERAL_CHANGE:0.0007; UNILATERAL_CHANGE:0.0005; UNILATERAL_CHANGE:0.0000 | 0.60 | LOW_SCORE | authority_subject | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sm-17 | FN | UNFAIR_DAMAGE_CLAIM → ∅ | UNFAIR_DAMAGE_CLAIM:0.0638; UNFAIR_DAMAGE_CLAIM:0.0008; UNFAIR_DAMAGE_CLAIM:0.0003 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sw-01 | FN | UNPAID_ADDITIONAL_WORK → ∅ | UNILATERAL_CHANGE:0.4339; UNPAID_ADDITIONAL_WORK:0.0319; UNPAID_ADDITIONAL_WORK:0.0126 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sw-04 | FP | ∅ → IP_TOTAL_FREE | IP_TOTAL_FREE:0.9056; IP_TOTAL_FREE:0.7845; IP_TOTAL_FREE:0.4763 | 0.60 | OVER_MATCH | none | gold=∅, predicted 존재, top-1 ≥ threshold | INFERRED |
| v4-sw-13 | FN | UNPAID_ADDITIONAL_WORK → ∅ | UNPAID_ADDITIONAL_WORK:0.0614; UNFAIR_DAMAGE_CLAIM:0.0197; UNPAID_ADDITIONAL_WORK:0.0053 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |
| v4-sw-17 | FN | UNFAIR_DAMAGE_CLAIM → ∅ | UNFAIR_DAMAGE_CLAIM:0.0018; UNFAIR_DAMAGE_CLAIM:0.0005; UNFAIR_DAMAGE_CLAIM:0.0001 | 0.60 | LOW_SCORE | negation | gold 후보가 top-3에 존재하지만 최고점 < threshold | INFERRED |

## 6. 결론과 해석 한계

- v3/v4의 현재 독소 오류는 저장된 top-3 근거 기준으로 `SEARCH_MISS`가 아니라, 후보가 낮은 FN(`LOW_SCORE`)과 정상 조항의 고점 오탐(`OVER_MATCH`)으로 모두 설명된다.
- v4에서는 FN 16건 중 `authority_subject` 7건, `negation` 9건이 골든 trap과 연결된다. 이는 의미 차원별 관찰값이지 법적 위험 판정이 아니다.
- `period`와 `UNMAPPED_PATTERN`은 현재 62개 오류에서 확인되지 않았다. 0건이라는 결과는 부재를 증명하는 것이 아니라, 이번 입력과 제한된 대조 범위에서 확인되지 않았다는 뜻이다.
- `UNMAPPED_PATTERN`은 gold/top-3만으로 부여하지 않는다. 이후 새 검토 패턴 후보를 기록할 때는 원문 문구, 대조한 기존 패턴 목록, 대응하지 않는 이유를 함께 남겨야 한다.
