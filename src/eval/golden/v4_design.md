# v4 골든셋 설계 문서 (`v4_design.md`)

본 문서는 v3 대비 독립적인 held-out 검증을 수행하기 위해 새롭게 설계된 v4 골든셋 54건에 대한 매트릭스 명세서입니다.

> [!WARNING]
> **데이터셋 용도 및 특성 주의**
> - 본 v4 골든셋은 **독소 조항에 대한 hard-negative challenge set**으로 기획되었습니다.
> - **이탈 검증(성능 비교 및 튜닝)에는 적합하지 않습니다.** SI 및 SW 계약 유형에는 이탈 양성(EXTRA 등) 케이스가 부재하여, 유형별 Precision/Recall/F1 등의 이탈 지표를 모델 성능 평가나 임계값(Threshold) 변경의 타당한 근거로 채택할 수 없습니다.

## 1. 케이스 매트릭스 설계 원칙

- **전체 규모:** 총 54건 (Tuning 36건, Held-out 18건)
- **계약유형별 균등 배분:** SI(18건), SM(18건), SW(18건)
- **쌍 단위 Split 격리:** 양성(독소)과 음성(hard-negative) 쌍은 반드시 동일한 split(Tuning 또는 Held-out) 내에 존재하여 데이터 정보 유출을 완벽하게 격리합니다.
- **법령 앵커 참조:** 각 케이스는 `v4_legal_anchors.md`에 기술된 법령 앵커 ID만 참조하며, 골든 JSON의 `gold_toxic` 라벨링과 기계적으로 연계되지 않습니다.
- **신규 위험 처리:** 현재 `ToxicPattern` enum에 속하지 않는 위협은 `gold_toxic: []`로 두고, `unmapped_review_candidate` 필드로 설계 테이블에 기록합니다.

---

## 2. 케이스 설계 매트릭스

### A. SI Subcontract (18건)

| Case ID | Split | Type | Deviation | Toxic Pattern | Trap | 법령 앵커 ID | 설명 / 비고 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **v4-si-01** | Tuning | 양성 | `NONE` | `UNPAID_ADDITIONAL_WORK` | `negation` | `LEGAL_ANCHOR_1` | 발주처 증액 예산이 미배정될 시 추가 대금 정산 불가 |
| **v4-si-02** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_1` | 발주처 예산 여부와 무관히 추가작업 대금 정산 보장 (Hard-Negative) |
| **v4-si-03** | Tuning | 양성 | `NONE` | `IP_TOTAL_FREE` | `party` | `LEGAL_ANCHOR_3` | 공동개발 산출물의 모든 권리와 2차 저작물권을 일방에게 무상 독점 귀속 |
| **v4-si-04** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_3` | 기여도에 따른 공동 소유 및 처분 동의권 보장 (Hard-Negative) |
| **v4-si-05** | Tuning | 양성 | `NONE` | `INDEFINITE_CONFIDENTIALITY` | `negation` | `LEGAL_ANCHOR_4` | 계약 종료/해지 이후에도 무제한/영구적 비밀유지 의무 부과 |
| **v4-si-06** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 비밀유지 의무 기간을 계약 종료 후 2년으로 한정 명시 (Hard-Negative) |
| **v4-si-07** | Tuning | 양성 | `NONE` | `UNILATERAL_INTERPRETATION` | `party` | `LEGAL_ANCHOR_6` | 조항 의미 이견 발생 시 원사업자의 일방적 판단 및 해석에 구속됨 |
| **v4-si-08** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_6` | 모호한 조항은 상호 대등한 합의 및 관계 법령에 기초하여 해석함 (Hard-Negative) |
| **v4-si-09** | Tuning | 양성 | `NONE` | `UNFAIR_DAMAGE_CLAIM` | `negation` | `LEGAL_ANCHOR_5` | 채무불이행 시 실질 손해와 무관하게 무조건 계약대금의 2배 위약벌 청구 |
| **v4-si-10** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_5` | 인과관계가 증명된 상대방의 고의·과실 직접 실손해 범위로 배상 한정 (Hard-Negative) |
| **v4-si-11** | Tuning | 양성 | `NONE` | `UNILATERAL_CHANGE` | `party` | `LEGAL_ANCHOR_2` | 원사업자 경영상 필요로 언제든지 위탁 임의취소/과업 일방변경 및 보상배제 |
| **v4-si-12** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_2` | 위탁 취소/변경 시 사전 서면 합의 및 기성 발생 비용에 대한 보전 보장 (Hard-Negative) |
| **v4-si-13** | Held-out | 양성 | `NONE` | `UNPAID_ADDITIONAL_WORK` | `negation` | `LEGAL_ANCHOR_1` | 구두 및 긴급 지시로 진행된 모든 보완 및 추가 작업은 무상 완수 강제 |
| **v4-si-14** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_1` | 긴급 추가 작업 시에도 사후 서면 확인서 및 추가 대금 정산 보장 (Hard-Negative) |
| **v4-si-15** | Held-out | 양성 | `NONE` | `IP_TOTAL_FREE` | `party` | `LEGAL_ANCHOR_3` | 수급인이 계약 이전 독자 보유했던 기존 핵심 기술(Pre-existing IP)도 양도 귀속 |
| **v4-si-16** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_3` | 기존 기술의 소유권은 수급인에게 존속하며 사용 라이선스만 허락함 (Hard-Negative) |
| **v4-si-17** | Held-out | 양성 | `NONE` | `INDEFINITE_CONFIDENTIALITY` | `negation` | `LEGAL_ANCHOR_4` | 본 계약 효력 상실 후에도 기한 제한 없이 무기한 영구적 비밀 보장 의무 |
| **v4-si-18** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 비밀정보 보존 및 준수 의무를 계약 해지일로부터 3년으로 제한 (Hard-Negative) |

---

### B. SM Subcontract (18-건)

| Case ID | Split | Type | Deviation | Toxic Pattern | Trap | 법령 앵커 ID | 설명 / 비고 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **v4-sm-01** | Tuning | 양성 | `NONE` | `UNPAID_ADDITIONAL_WORK` | `negation` | `LEGAL_ANCHOR_1` | 기본 유지관리 범위를 초과하는 신규 기능 추가 패치를 무상 요구 및 강제 |
| **v4-sm-02** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_1` | 기본 범위를 벗어나는 유지관리 추가 작업은 별도 합의 대금 정산 (Hard-Negative) |
| **v4-sm-03** | Tuning | 양성 | `NONE` | `IP_TOTAL_FREE` | `party` | `LEGAL_ANCHOR_3` | 유지관리 중 개선 코드와 소스 패치 저작권을 전적으로 원사업자 독점 귀속 |
| **v4-sm-04** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_3` | 패치 및 업그레이드 판권은 기존 개발자 소유로 하되 무상 사용권 부여 (Hard-Negative) |
| **v4-sm-05** | Tuning | 양성 | `NONE` | `INDEFINITE_CONFIDENTIALITY` | `negation` | `LEGAL_ANCHOR_4` | 시스템 접속 중 취득한 일체 기술 사양에 대해 영구 비밀 의무 부과 |
| **v4-sm-06** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 시스템 접근 영업비밀 유지 준수 기간을 계약 종료 시점부터 1년 한정 (Hard-Negative) |
| **v4-sm-07** | Tuning | 양성 | `NONE` | `UNILATERAL_INTERPRETATION` | `party` | `LEGAL_ANCHOR_6` | 유지관리 장애 수준 및 검수 합격 통지 여부는 원사업자 독단적 해석에 따름 |
| **v4-sm-08** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_6` | 장애 및 긴급도 판단은 계약서상 SLA(서비스수준약정)의 정량적 기준 준용 (Hard-Negative) |
| **v4-sm-09** | Tuning | 양성 | `NONE` | `NONCOMPETE_EXCESS` | `negation` | `LEGAL_ANCHOR_4` | 유지보수 계약 종료 후 3년간 경쟁사에 대한 동종 유지관리 서비스 전면 금지 |
| **v4-sm-10** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 계약 종료 시점 이후 경업을 특별 제약하지 않고 일반적 비밀유지만 준수 (Hard-Negative) |
| **v4-sm-11** | Tuning | 양성 | `NONE` | `UNILATERAL_CANCELLATION` | `party` | `LEGAL_ANCHOR_2` | 시스템 교체 등 원사업자 사정으로 1주일 전 통지로 무보상 즉각 일방 해지 |
| **v4-sm-12** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_2` | 계약 해지 시 최소 1개월 전 서면 통보 및 잔여 기간 기성 발생 비례 정산 (Hard-Negative) |
| **v4-sm-13** | Held-out | 양성 | `NONE` | `NONCOMPETE_EXCESS` | `negation` | `LEGAL_ANCHOR_4` | 유지보수 인력이 퇴사 후 2년 내 이직 시 보수 총액의 100%를 위약벌 배상 |
| **v4-sm-14** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 기술 유출 방지 및 직업 선택 자유를 부당 제한하지 않는 범위로 조율 (Hard-Negative) |
| **v4-sm-15** | Held-out | 양성 | `NONE` | `UNILATERAL_CHANGE` | `party` | `LEGAL_ANCHOR_2` | 유지보수 대상 시스템의 대상을 원사업자가 임의 추가/변경하되 용역비는 동결 |
| **v4-sm-16** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_2` | 유지관리 대상 및 규모가 추가·변경될 시 단가를 상호 비례하여 재조정함 (Hard-Negative) |
| **v4-sm-17** | Held-out | 양성 | `NONE` | `UNFAIR_DAMAGE_CLAIM` | `negation` | `LEGAL_ANCHOR_5` | 일시적 장애시간 1시간당 월 전체 유지보수료의 전액을 공제 상계 처리함 |
| **v4-sm-18** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_5` | SLA에 근거하여 장애 발생 시간별 비례 지체이율에 따라 한도 내에서 상계 (Hard-Negative) |

---

### C. SW Freelance (18건)

| Case ID | Split | Type | Deviation | Toxic Pattern | Trap | 법령 앵커 ID | 설명 / 비고 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **v4-sw-01** | Tuning | 양성 | `NONE` | `UNPAID_ADDITIONAL_WORK` | `negation` | `LEGAL_ANCHOR_1` | 원래 업무 범위 밖의 프로그램 추가 보완 및 수정을 프리랜서 무상 완수로 규정 |
| **v4-sw-02** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_1` | 기획 외 추가 작업 지시 시 별도 단가에 따라 사후 정산을 서면 보장함 (Hard-Negative) |
| **v4-sw-03** | Tuning | 양성 | `NONE` | `IP_TOTAL_FREE` | `party` | `LEGAL_ANCHOR_3` | 프리랜서가 창작한 소스코드 및 지식재산권을 원사업자가 영구 무상 독점 소유 |
| **v4-sw-04** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_3` | 소스코드 지식재산권을 공동 소유하며, 상호 실시 동의 및 이용을 허용함 (Hard-Negative) |
| **v4-sw-05** | Tuning | 양성 | `NONE` | `INDEFINITE_CONFIDENTIALITY` | `negation` | `LEGAL_ANCHOR_4` | 용역 완수 이후에도 영구히 기술 지식 및 노하우를 영업비밀로 묶어 이직 시 제한 |
| **v4-sw-06** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 프리랜서의 기밀유지 의무 기한을 용역 종료일로부터 1년 이내로 제한함 (Hard-Negative) |
| **v4-sw-07** | Tuning | 양성 | `NONE` | `UNILATERAL_INTERPRETATION` | `party` | `LEGAL_ANCHOR_6` | 프리랜서 계약상의 모든 조항 문구에 대한 해석 권한은 전적으로 발주사에 귀속됨 |
| **v4-sw-08** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_6` | 애매한 조항은 양사 공동 협의 및 민법상 계약 상충 해결 규칙을 기본 준용 (Hard-Negative) |
| **v4-sw-09** | Tuning | 양성 | `NONE` | `UNFAIR_DAMAGE_CLAIM` | `negation` | `LEGAL_ANCHOR_5` | 단순 지연 발생 시에도 즉시 계약을 파기하고 전체 계약금의 2배 위약벌 배상 청구 |
| **v4-sw-10** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_5` | 프리랜서의 고의·과실로 상대가 입은 입증된 실제 직접 손실만 한정 배상 (Hard-Negative) |
| **v4-sw-11** | Tuning | 양성 | `NONE` | `UNILATERAL_CANCELLATION` | `party` | `LEGAL_ANCHOR_2` | 발주사는 필요에 따라 임의 해지할 수 있으며 취소 시점까지의 기성은 정산 안 함 |
| **v4-sw-12** | Tuning | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_2` | 해지 시 15일 전 통보를 요하며 이행 완료된 기성에 대해 대금을 서면 정산함 (Hard-Negative) |
| **v4-sw-13** | Held-out | 양성 | `NONE` | `UNPAID_ADDITIONAL_WORK` | `negation` | `LEGAL_ANCHOR_1` | 검수 불합격 시 검수 통과할 때까지 추가 요구 보완 개발을 무상으로 영구 수행함 |
| **v4-sw-14** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_1` | 합의 규격 외 추가 검수 보완 요구는 용역비 가산 및 신규 위탁 계약 체결 (Hard-Negative) |
| **v4-sw-15** | Held-out | 양성 | `NONE` | `INDEFINITE_CONFIDENTIALITY` | `negation` | `LEGAL_ANCHOR_4` | 용역 수행을 위해 취득한 기술 지식 전반에 대해 기한 없이 영구적 비밀 의무 |
| **v4-sw-16** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_4` | 기밀 자료 준수 기간을 개발 완료 후 2년 내로 명확히 기한 한정 (Hard-Negative) |
| **v4-sw-17** | Held-out | 양성 | `NONE` | `UNFAIR_DAMAGE_CLAIM` | `negation` | `LEGAL_ANCHOR_5` | 1일 납기 지연 시 기성 대금의 10%를 삭감하는 과도한 지체상금 부과 조항 (1일당 기성 10% 삭감) |
| **v4-sw-18** | Held-out | 음성 | `NONE` | 없음 | `none` | `LEGAL_ANCHOR_5` | 귀책사유와 요율·기간·상한을 당사자 합의로 특정한 지체상금 사례 (Hard-Negative) |

---

## 3. 신규 위험 탐색 및 후보 기록 (`unmapped_review_candidate`)

- **사례:** `v4-sw-05` 등 비밀유지 조항 및 정보 공개 위험
- **설명:** 비밀정보 범위가 불분명하거나 프리랜서가 합법적 용도로도 제3자에게 소스코드 공유를 못 하도록 전면 금지하는 등의 위험이 존재하나, 이는 현 `ToxicPattern`에 속하지 않으므로 골든 JSON 스키마에는 `gold_toxic: []`로 적고 본 설계 명세서 상에만 분석하여 기록함.

---

## 4. 변경 이력 (Revision History)

### 2026-07-12: 변경 전 v4 기준선 기록 (P0-1)

v4 골든셋과 법령 앵커 정합성 수정 전의 기준선을 아래와 같이 기록합니다.

- **기반 Git Commit:** `2219e8ba63e240bec17ac10ccb57f9912a3068d1`
- **데이터셋 구성:**
  - 총 54건 (Tuning 36건, Held-out 18건)
  - 계약 유형별 SI·SM·SW 각 18건
- **평가 기준 설정:**
  - `match_threshold`: `0.50`
  - `toxic_threshold`: `0.60`
- **검색 및 재정렬 성능:**
  - `hybrid_5_5`: Recall@5 `0.729`, MRR `0.607`
  - `hybrid_rerank_5_5`: Recall@5 `0.729`, MRR `0.581`
- **독소 held-out 성능 지표:**
  - 혼동 행렬: TP `2`, FP `0`, FN `7`, TN `9`
  - Precision: `1.000`, Recall: `0.222`, F1: `0.364`
- **수정 전 주요 파일 SHA-256 해시:**
  - `v4_design.md`: `642dbd6e…79b6a`
  - `v4_sw_freelance.json`: `7066543e…619a`
  - `threshold_heldout.v4.json`: `66ea1591…b1e`
  - `v4_result.md`: `65af415b…bdf`
  - `v4_diagnostics.json`: `5cd6863b…fca4`
  - `v4_diagnostics.md`: `0b38573b…24fb`
  - `v4_legal_anchors.md`: `580ba266…e9`

### 2026-07-12: 변경 후 v4 기준선 및 재평가 기록

가치 판단을 배제하는 프레이밍(`v4-sw-18` 및 법령 앵커 완화 등)을 수용하여 `prod` 환경에서 재평가를 거친 지표와 해시 정보를 기록합니다.

- **재평가 실행 시각 및 환경:** `2026-07-12 19:50:43`, `APP_ENV=prod`
- **변경 후 기준선:** 본 변경을 포함하는 Git 커밋으로 동결한다. 커밋 식별자는 Git 이력으로 관리한다.
- **검색 및 재정렬 성능:**
  - `hybrid_5_5`: Recall@5 `0.729`, MRR `0.607` (07-11.md 인용 기준값)
  - `hybrid_rerank_5_5`: Recall@5 `0.688`, MRR `0.567` (P0-2 문구 정정에 따른 재배치로 Recall@5 0.041 감소, MRR 0.004 감소)
- **독소 held-out 성능 지표:**
  - 혼동 행렬: TP `2`, FP `0`, FN `7`, TN `9` (Precision `1.000`, Recall `0.222`, F1 `0.364`로 변동 없음)
- **동결 대상 원천 파일 5종 SHA-256 해시:**
  - `v4_si_subcontract.json`: `651ca5f4bdb5d4a6f1109c5f9c8cabefc1f375af458dc37843317541e59cdb49` (수정됨)
  - `v4_sm_subcontract.json`: `f8c7ad61ec93b920da4316ea5ea2cd080dda3255068a958b87ae33a096984a6c` (수정됨)
  - `v4_sw_freelance.json`: `33a95ad01bb3af922f18aaa1525016b083824116a8b6eac92f6c4d3d4c29bb46` (수정됨)
  - `threshold_heldout.v4.json`: `66ea1591d30ed813e7128262179fd72d2a47574cafd263bcefaf975e97424ccb` (변경 없음)
  - `v4_legal_anchors.md`: `12cb4b23e626d3f85729888068477653011956be2adb6956da5963229929ccc7` (피드백 반영 수정됨)

*(참고: v4_design.md 자기 자신의 해시는 자기참조 문제를 방지하기 위해 파일 내 기록에서 제외하며, 평가 결과 및 진단 파일 3종은 Git 커밋 ID 및 실행 설정으로 관리하므로 본 해시 목록에서 배제합니다.)*
