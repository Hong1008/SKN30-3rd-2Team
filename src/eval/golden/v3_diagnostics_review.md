# v3 — case-level 진단 리뷰

> 2026-07-12 · `just eval a v3 prod` 재실행 결과를 기준으로 작성. 법률적 결론이 아니라
> 검색·매칭·패턴 분류의 **검토 후보** 오류 분석이다.

## 1. trace 정합성

- `review_contract` 실행 중의 rerank 결과를 eval 프록시가 직접 보존하도록 변경했다.
- 재생성된 `v3_diagnostics.json`에서 `matched_standard`가 top-3 후보 또는 서브청크의 부모에
> 없는 사례는 **0건**이다.
- 이전 별도 재검색 방식에서 발생했던 후보 불일치 7건은 제거됐다. 이후 후보 점수·출처는 최종
> 판정과 동일 실행의 근거로 해석할 수 있다.

## 2. 이탈

| 항목 | TP | FP | FN | TN | 해석 |
| --- | ---: | ---: | ---: | ---: | --- |
| 전체 | 30 | 7 | 12 | 68 | FN은 모두 높은 점수의 `OVER_MATCH` |
| SI | 9 | 3 | 6 | 27 | 최우선 분석 대상 |
| SM | 12 | 4 | 3 | 26 | 정상 조항 under-match가 남음 |
| SW | 9 | 0 | 3 | 15 | 정밀도는 높고 over-match만 남음 |

- FN은 `v3-si-41`(0.867), `v3-si-44`(0.99998), `v3-si-45`(0.99980)처럼 기본
  `match_threshold=0.50`보다 훨씬 높다. 임계값 상향만으로는 해결되지 않는다.
- FP 7건은 대부분 낮은 score의 `UNDER_MATCH`다. 다만 held-out에서 threshold 개선이 재현되지
  않았으므로 기본 임계값은 유지한다.

## 3. 독소 FP — 수동 대조

독소 FP는 31건이다. 다수가 0.90 이상이라 threshold 조정만으로 제거할 수 없다.

| 대표 case | 정상/비독소 문구의 핵심 | 잘못 매칭된 pattern | 관찰 |
| --- | --- | --- | --- |
| `v3-si-12` | 추가작업은 동의·지시서·추가대금 지급이 필요 | `UNPAID_ADDITIONAL_WORK` 0.986 | 같은 “추가작업” 주제지만 **지급 보장**과 **무상 강제**의 극성을 구분 못 함 |
| `v3-sw-06` | 비밀준수 기간은 업무 종료 후 1년 | `INDEFINITE_CONFIDENTIALITY` 0.991 | 비밀유지 주제만 보고 **기한 한정**을 무시 |
| `v3-sw-10` | 지식재산권 공동소유 | `IP_TOTAL_FREE` 0.991 | 공동소유와 전부·무상 귀속의 소유권 범위를 구분 못 함 |
| `v3-sw-23` | 법령 및 상호 합의로 계약 해석 | `UNILATERAL_INTERPRETATION` 0.99998 | 상호협의와 일방 해석의 당사자 권한을 구분 못 함 |
| `v3-sw-25` | 종료 시 기술정보 반환·파기 | `INDEFINITE_CONFIDENTIALITY` 0.996, `UNILATERAL_CANCELLATION` 0.995 | 반환 의무를 영구 비밀유지·일방해지와 혼동 |

추가 관찰:

- `v3-sw-08`은 비밀정보를 서면동의 없이 유출할 수 있게 하는 별도 위험 표현이지만, 현재
  `gold_toxic=[]`이며 탐지기는 `INDEFINITE_CONFIDENTIALITY`로만 잡는다. 이는 단순 FP뿐 아니라
  **현 ToxicPattern 분류체계에 없는 위험 유형**일 가능성을 보여준다. 새 pattern 추가 또는 gold
  라벨 변경은 v4 작성 시 사람 검토·사인오프가 필요하다.
- SI/SM의 목적조항(`v3-si-01`, `v3-sm-01`)도 IP·일방해석 패턴에 0.99로 매칭된다. 긴 조항이나
  공통 당사자어휘만으로도 과매칭하는 현상이 있다.

## 4. 독소 FN — 수동 대조

독소 FN은 10건이며 top-1 score가 모두 0.032 이하다. 임계값을 0.60보다 낮추는 방식은 대량 FP를
늘릴 뿐 FN을 안정적으로 해결하지 못한다.

| 대표 case | gold pattern | top 후보 / score | 관찰 |
| --- | --- | --- | --- |
| `v3-si-31` | `NONCOMPETE_EXCESS` | 같은 pattern 0.0005 | 경쟁 제한 기간·위약벌 표현이 예문과 가깝지만 점수가 붕괴 |
| `v3-sm-31` | `INDEFINITE_CONFIDENTIALITY` | 같은 pattern 0.0237 | “기간 한정 없이 영구”가 예문과 직접 유사하지만 점수가 붕괴 |
| `v3-sm-32` | `UNPAID_ADDITIONAL_WORK` | 같은 pattern 0.0035 | 무상 추가 패치·초과 용역을 탐지하지 못함 |
| `v3-sw-17` | `UNFAIR_DAMAGE_CLAIM` | 같은 pattern 0.0204 | 계약금액 20% 정액 위약금과 예문의 지연 위약금이 유사 |
| `v3-sm-33` | `UNFAIR_DAMAGE_CLAIM`, `UNILATERAL_CHANGE` | 무관 `NONCOMPETE_EXCESS` 0.0088 | 승인 없는 패치에 대한 월 기성금 50% 삭감이 패턴 검색에서 누락 |

이 사례들은 단순 코퍼스 어휘 부족으로 보기 어렵다. gold와 같은 pattern 예문이 top 후보에 있어도
score가 극단적으로 낮은 경우가 있으므로, 다음 작업에서 prod reranker 반복 실행 변동성과 입력
형식·배치 효과를 우선 측정해야 한다.

## 5. 후속 결정

1. `match_threshold`와 `toxic_threshold` 기본값은 현행 유지.
2. 독소 개선은 데이터 증식보다 **극성·당사자 역할·기간·대가·권한**이 반대인 hard-negative를
   v4 held-out에 추가해 검증한다.
3. `NONCOMPETE_EXCESS`, `INDEFINITE_CONFIDENTIALITY`, `UNFAIR_DAMAGE_CLAIM`,
   `UNPAID_ADDITIONAL_WORK`의 같은-pattern 저점 현상은 prod reranker 반복 실행 변동성 측정 후
   개선안을 결정한다.
4. 새 위험 유형(예: 비밀정보 무단 공개 허용)은 ToxicPattern 확장 여부를 별도 사인오프 카드로
   다룬다. 1차 파이프라인은 해석·위법 판정을 생성하지 않는다.
