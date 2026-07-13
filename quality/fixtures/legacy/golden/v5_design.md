# v5 이탈 평가 골든셋 설계

본 문서는 v4의 유형별 이탈 양성 불균형을 보완하기 위한 별도 이탈 평가 트랙의 설계 명세다.
v5는 결정론적 이탈 P/R/F1 평가와 EXTRA 고점 과매칭 진단에 사용한다.

> **범위:** 문서·케이스 구성·held-out manifest 설계만 다룬다. 동결된 골든 JSON 스키마,
> MCP 계약, 프로덕션 임계값은 변경하지 않는다.

## 1. 고정 정책

- 골든 케이스의 `gold_deviation`은 기존 동결 enum인 `NONE`/`EXTRA`만 사용한다.
- 모든 EXTRA 케이스는 `gold_clause_id=null`로 둔다.
- EXTRA 케이스가 표준조항과 혼동되도록 설계된 경우, 비교 대상은 이 문서의
  `contrast_clause_id`로만 기록한다. 이는 정답 표준조항·검색 Recall/MRR 집계에는 사용하지 않고,
  고점 과매칭 진단에만 사용한다.
- `contrast_reason`은 같은 주제·명사·수치·기간·당사자 표현 등 혼동을 설계한 근거다.
- `gold_toxic`은 기존 `ToxicPattern` enum에 정확히 대응하는 경우에만 기록한다.
  검토 강화 EXTRA라는 분류나 법적 판단을 근거로 자동 부여하지 않는다.
- 사용자 표면 문구와 `note`는 법적 결론이 아니라 사람이 확인할 검토 후보로 작성한다.

### 케이스 명칭

| 설계 명칭 | `gold_deviation` | 의미 | `gold_toxic` |
| --- | --- | --- | --- |
| 검토 강화 EXTRA | `EXTRA` | 고점 과매칭과 이탈 탐지를 함께 확인할 EXTRA | 해당할 때만 기록 |
| 일반 EXTRA | `EXTRA` | 독소 패턴 없이 이탈 이진 평가에 포함되는 EXTRA | 대체로 `[]` |
| 표준 대응 NONE | `NONE` | 표준조항에 대응하는 정상 케이스 | 해당할 때만 기록 |

검토 강화/일반은 평가용 설계 층위이며 별도 JSON 필드나 enum이 아니다. 구분은 케이스 ID,
`note`, `gold_toxic`, 그리고 본 문서의 매트릭스로 관리한다.

## 2. 전체 규모와 split

| 계약 유형 | Tuning | Held-out | 합계 |
| --- | ---: | ---: | ---: |
| SI_SUBCONTRACT | 30 | 15 | 45 |
| SM_SUBCONTRACT | 30 | 15 | 45 |
| SW_FREELANCE | 30 | 15 | 45 |
| **합계** | **90** | **45** | **135** |

각 split의 유형별 최소 구성은 다음과 같다.

| Split | 검토 강화 EXTRA | 일반 EXTRA | 표준 대응 NONE | 합계 |
| --- | ---: | ---: | ---: | ---: |
| Tuning | 10 | 10 | 10 | 30 |
| Held-out | 5 | 5 | 5 | 15 |

Held-out에는 유형별로 이탈 양성(`EXTRA`) 10건과 이탈 음성(`NONE`) 5건이 있으므로,
유형별 이탈 P/R/F1 및 혼동행렬을 계산할 수 있다. 검토 강화/일반 EXTRA는 모두 이탈 이진
지표의 양성으로 집계한다.

## 3. 주제 그룹과 split 격리

한 주제 그룹은 아래 세 케이스로 구성한다.

```text
topic_group
├── 검토 강화 EXTRA
├── 일반 EXTRA
└── 표준 대응 NONE
```

- 유형별 Tuning 10개 그룹, Held-out 5개 그룹을 만든다.
- 그룹 전체를 Tuning 또는 Held-out 한쪽에만 배치한다.
- 양성·음성 쌍, 동일 표준조항, 동일 핵심 명사, 동일 숫자·기간 변형은 같은 그룹으로 묶는다.
- Held-out에는 Tuning의 단순 문장 치환·숫자 치환·당사자 치환을 재사용하지 않는다.
- 같은 법적 주제를 유형 간 사용할 수 있으나, 문장·수치·당사자 조합은 독립적으로 작성한다.

### 그룹 ID 계획

| 유형 | Tuning 그룹 | Held-out 그룹 | 케이스 ID 규칙 |
| --- | --- | --- | --- |
| SI | `si-t01`~`si-t10` | `si-h01`~`si-h05` | `v5-si-01`~`v5-si-45` |
| SM | `sm-t01`~`sm-t10` | `sm-h01`~`sm-h05` | `v5-sm-01`~`v5-sm-45` |
| SW | `sw-t01`~`sw-t10` | `sw-h01`~`sw-h05` | `v5-sw-01`~`v5-sw-45` |

그룹별 케이스 순서는 `검토 강화 EXTRA → 일반 EXTRA → 표준 대응 NONE`으로 고정한다.
따라서 그룹당 3건, split별 10개 또는 5개 그룹이 각각 30건 또는 15건을 구성한다.

## 4. 케이스 매트릭스 작성 규격

실제 골든 JSON 작성 전, 사람 검토용 매트릭스에는 다음 열을 둔다.

| 열 | 용도 |
| --- | --- |
| `case_id` | 골든 케이스 ID |
| `topic_group` | split 격리 단위 |
| `split` | `TUNING` 또는 `HELD_OUT` |
| `contract_type` | SI/SM/SW 유형 |
| `design_role` | 검토 강화 EXTRA / 일반 EXTRA / 표준 대응 NONE |
| `gold_deviation` | 동결 enum 값 |
| `gold_clause_id` | NONE만 실제 표준조항 ID, EXTRA는 `null` |
| `contrast_clause_id` | EXTRA의 혼동 대상 표준조항 ID; 진단 전용 |
| `contrast_reason` | 고점 과매칭 혼동 설계 근거 |
| `gold_toxic` | 기존 enum에 정확히 대응할 때만 기록 |
| `trap` | 기존 trap enum 값 |
| `note` | 사람 검토용 설명 |

`contrast_clause_id`가 표준 코퍼스에 실제 존재하는지는 사람 검토와 별도 정적 확인 대상으로
삼는다. 그러나 `gold_clause_id`가 아니므로 검색 정답으로 취급하지 않는다.

## 5. 함정 분포

각 계약 유형의 각 split에서 다음 최소 조건을 만족시킨다.

- `paraphrase`, `partial`, `reorder` 각각 최소 1개
- `number`, `negation`, `party`, `contradiction` 중 최소 2개 이상
- 표준 대응 NONE만 단순 `none`으로 구성하지 않고, 일부는 말바꿈·순서 변경을 포함한다.
- 일반 EXTRA에도 검토 강화 EXTRA와 유사한 핵심 어휘를 사용해 lexical shortcut을 피한다.

최종 매트릭스에서는 함정별 실제 건수를 표로 집계하고, 어느 한 함정이 특정 split에만 몰리지
않도록 사람 검토자가 확인한다.

## 6. 지표 정의

### 6.1 기본 이탈 이진 지표

- 양성: 검토 강화 EXTRA + 일반 EXTRA (`gold_deviation=EXTRA`)
- 음성: 표준 대응 NONE (`gold_deviation=NONE`)
- 유형별로 TP/FP/FN/TN, Precision, Recall, F1을 계산한다.
- 전체 합산 지표도 별도로 계산한다.

### 6.2 보조 진단 지표

- 검토 강화 EXTRA recall
- 일반 EXTRA recall
- 표준 대응 NONE false-positive rate
- `contrast_clause_id` 고점 과매칭 수
- 계약 유형별 F1의 산술평균인 전체 macro-F1

### 6.3 전체 macro-F1의 평균 축

전체 macro-F1은 Held-out의 SI·SM·SW 유형별 F1을 산술평균한 값이다.
유형별 표본 수가 같더라도 전체 합산 F1과 구분해 함께 기록한다.

결과에는 다음을 모두 포함한다.

1. 유형별 TP/FP/FN/TN, Precision/Recall/F1
2. 유형별 F1의 산술평균인 전체 macro-F1
3. 전체 케이스 합산 TP/FP/FN/TN 및 합산 Precision/Recall/F1
4. 보조 진단 지표 일람

## 7. 고점 과매칭 수치 기준

EXTRA 케이스에서 실제 최종 매칭 표준조항이 `contrast_clause_id`와 같고,
confidence가 현재 `match_threshold` 이상인 경우를 고점 과매칭으로 집계한다.

- 프로덕션 기준: `confidence >= 0.50`
- 후보 실험 기준: 각 후보 threshold를 별도 표에 기록
- 후보 기준 결과와 프로덕션 기준 `0.50` 결과를 섞지 않는다.
- 고점 과매칭은 이탈 정답 판정이나 검색 Recall/MRR의 정답으로 사용하지 않는다.

## 8. 임계값 정책

Tuning은 실험 임계값 후보를 비교하는 용도로만 사용한다. Held-out 결과와 별도 사람 승인
없이는 프로덕션 임계값을 변경하지 않는다.

v5에서도 현재 프로덕션 기준선은 다음을 유지한다.

- `match_threshold=0.50`
- `toxic_threshold=0.60`

v5의 threshold sweep 결과는 후보 비교·진단 자료일 뿐 자동 채택 규칙으로 사용하지 않는다.

## 9. 사람 검토 체크리스트

- [ ] 유형별 Tuning 30건/Held-out 15건을 충족한다.
- [ ] 각 split에 검토 강화 EXTRA 10/5건, 일반 EXTRA 10/5건, 표준 대응 NONE 10/5건이 있다.
- [ ] 모든 EXTRA의 `gold_clause_id`가 `null`이다.
- [ ] 모든 EXTRA에 `contrast_clause_id`와 `contrast_reason`이 있다.
- [ ] `contrast_clause_id`는 진단 메타데이터로만 사용된다.
- [ ] `gold_toxic`은 기존 enum에 정확히 대응할 때만 기록된다.
- [ ] 동일 `topic_group`이 split을 넘지 않는다.
- [ ] Held-out에 Tuning의 단순 표현 재사용이 없다.
- [ ] 유형별 TP/FP/FN/TN과 합산 지표, macro-F1 산식이 분리된다.
- [ ] 임계값 후보 결과와 프로덕션 기준 0.50 결과가 분리된다.

## 10. 산출물과 승인 경계

- `threshold_heldout.v5.json`의 기계 판정 기준은 `heldout_case_ids`다. `purpose`, `selection`,
  `production_thresholds`, `case_id_policy` 같은 설명용 메타데이터를 함께 둘 수 있으며,
  이 메타데이터는 held-out 케이스 판정이나 평가 집계를 변경하지 않는다.
- 실제 `v5_<contract_type>.json`은 본 설계 승인 후 별도 작성한다.
- 본 설계와 held-out 목록 승인 전에는 평가 실행 결과를 임계값 변경 근거로 사용하지 않는다.
- 모든 EXTRA 케이스는 `gold_clause_id=null`을 유지하고, 혼동 표준조항은 설계 문서의
  `contrast_clause_id`로만 기록한다.
