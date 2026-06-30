# 독소조항 추가 후보 목록

> 추가 전 팀 합의 필요 — AGENTS.md 규칙 #2 (동결 계약 임의 변경 금지)
>
> 작업 순서: ① enum 합의 → ② `toxic_patterns.json` 추가 → ③ `just build-db`

---

## 패턴 수 결정 근거

현재 5개 + 후보 4개 = **총 9개로 충분하다고 판단**.

| 영역 | 커버하는 패턴 |
| --- | --- |
| 지식재산권 | `IP_TOTAL_FREE` |
| 대금·보수 | `PAYMENT_DELAY_UNFAIR`, `UNPAID_ADDITIONAL_WORK` |
| 계약 이행 | `UNILATERAL_CHANGE`, `UNILATERAL_CANCELLATION` |
| 계약 해석·분쟁 | `UNILATERAL_INTERPRETATION` |
| 손해배상 | `UNFAIR_DAMAGE_CLAIM` |
| 비밀유지 | `NONCOMPETE_EXCESS`, `INDEFINITE_CONFIDENTIALITY` |

SW 프리랜서 계약에서 실질적으로 문제가 되는 주요 영역을 모두 포함한다.

---

## 현재 등록 현황

| pattern enum 값 | enum | json |
| --- | --- | --- |
| `NONCOMPETE_EXCESS` | ✅ | ✅ |
| `IP_TOTAL_FREE` | ✅ | ✅ |
| `PAYMENT_DELAY_UNFAIR` | ✅ | ✅ |
| `UNILATERAL_CHANGE` | ✅ | ❌ |
| `UNFAIR_DAMAGE_CLAIM` | ✅ | ❌ |

---

## A. json만 추가하면 되는 항목 (enum 이미 존재)

### A-1. `UNILATERAL_CHANGE` — 일방적 과업 범위 변경

- **출처:** `data/02_converted/201231_SW종사자_표준도급계약서.md` 제4조⑤
  > "본 계약 또는 부속서류에서 정한 업무와 관련된 사항에 대하여 당사자 간 서면 합의에 따라 변경할 수 있다. 다만, 도급인은 수급인이 업무의 변경에 합의하도록 부당한 행위를 하여서는 아니 된다."

```json
{
  "pattern_id": "toxic-unilateral_change-01",
  "pattern": "UNILATERAL_CHANGE",
  "category": "SCOPE_SOW",
  "title": "일방적인 과업 범위 변경 권한",
  "text": "도급인은 필요에 따라 수급인과의 사전 협의 없이 업무 범위, 납기일, 산출물 규격을 변경할 수 있으며, 수급인은 추가 보수 청구 없이 이에 응하여야 한다."
}
```

---

### A-2. `UNFAIR_DAMAGE_CLAIM` — 부당하게 과도한 손해배상 청구액

- **출처:** `data/02_converted/201231_SW종사자_표준도급계약서.md` 제6조③
  > "지체일수마다 지급액에 1000분의 1.25를 곱하여 산출한 금액을 공제한 후 지급" (표준 기준치 → 이를 크게 초과하면 독소)

```json
{
  "pattern_id": "toxic-unfair_damage_claim-01",
  "pattern": "UNFAIR_DAMAGE_CLAIM",
  "category": "LIABILITY",
  "title": "부당하게 과도한 손해배상 청구액 설정",
  "text": "수급인이 납기를 지키지 못하거나 도급인이 요구한 품질 기준을 충족하지 못할 경우, 수급인은 계약 보수 전액의 3배에 해당하는 금액을 손해배상액으로 지급하여야 ;한다."
}
```

---

## B. enum + json 모두 추가해야 하는 항목

### B-1. `UNILATERAL_INTERPRETATION` — 발주자의 일방적 계약 해석 권한

- **출처:** `data/toxic/프리랜서_불공정계약유형.md`
  > "계약사항과 관련하여 당사자 간 이견이 있을 경우 … 발주자 일방의 해석에 따르도록 하는 경우들이 있다."

**enum:**
```python
UNILATERAL_INTERPRETATION = "UNILATERAL_INTERPRETATION"
"""발주자의 일방적 계약 해석 권한"""
```

**json:**
```json
{
  "pattern_id": "toxic-unilateral_interpretation-01",
  "pattern": "UNILATERAL_INTERPRETATION",
  "category": "DISPUTE",
  "title": "발주자의 일방적 계약 해석 권한",
  "text": "본 계약 내용에 관하여 당사자 간 이견이 발생할 경우 도급인(발주자)의 해석 및 판단에 따르며, 수급인은 이에 이의를 제기하지 아니한다."
}
```

---

### B-2. `UNILATERAL_CANCELLATION` — 일방적 위탁 취소·계약 해지 (무보상)

- **출처 1:** `data/toxic/프리랜서_불공정계약유형.md`
  > "발주자의 일방적 계약해지가 가능하도록 한 불공정 조항이 다수 존재한다."
- **출처 2:** `data/02_converted/221228_상용소프트웨어_공급개발구축업.md` 제24조
  > "수급사업자의 책임으로 돌릴 수 있는 사유가 아니면 위탁을 임의로 취소하거나 변경하지 아니하다."

**enum:**
```python
UNILATERAL_CANCELLATION = "UNILATERAL_CANCELLATION"
"""발주자의 일방적 계약 해지 및 기이행 보수 미지급"""
```

**json:**
```json
{
  "pattern_id": "toxic-unilateral_cancellation-01",
  "pattern": "UNILATERAL_CANCELLATION",
  "category": "TERMINATION",
  "title": "발주자의 일방적 위탁 취소 및 무보상 계약 해지",
  "text": "도급인은 계약 이행 중이라도 사유의 여하를 불문하고 언제든지 본 계약을 해지할 수 있으며, 이 경우 수급인에게 기이행 부분에 대한 보수를 지급하지 아니하고 수급인은 이에 이의를 제기하지 아니한다."
}
```

---

### B-3. `INDEFINITE_CONFIDENTIALITY` — 무기한·과도한 비밀유지 기간

- **출처:** `data/02_converted/201231_SW종사자_표준도급계약서.md` 제17조④
  > "비밀 준수 기간은 업무 종료 후 1년으로 한다." (표준 기준 = 1년 → 무기한·장기간은 독소)

**enum:**
```python
INDEFINITE_CONFIDENTIALITY = "INDEFINITE_CONFIDENTIALITY"
"""계약 종료 후 무기한 또는 과도하게 장기간의 비밀유지 의무 부과"""
```

**json:**
```json
{
  "pattern_id": "toxic-indefinite_confidentiality-01",
  "pattern": "INDEFINITE_CONFIDENTIALITY",
  "category": "CONFIDENTIALITY",
  "title": "무기한·과도한 비밀유지 기간 설정",
  "text": "수급인은 본 계약 종료 후에도 기간의 제한 없이 영구적으로 도급인의 영업비밀 및 기술정보 일체를 제3자에게 공개하거나 본인의 영업 목적으로 활용할 수 없으며, 이를 위반할 경우 손해배상 책임을 진다."
}
```

---

### B-4. `UNPAID_ADDITIONAL_WORK` — 추가 업무 무상 강요

- **출처:** `data/02_converted/221228_상용소프트웨어_공급개발구축업.md` 제11조
  > "원사업자의 요구에 따라 수급사업자가 수행한 추가작업에 대하여 발주자로부터 증액받지 못한 경우에도 원사업자는 수급사업자에게 증액하여 지급한다."

**enum:**
```python
UNPAID_ADDITIONAL_WORK = "UNPAID_ADDITIONAL_WORK"
"""계약 범위 외 추가 업무를 별도 보수 없이 무상 수행 강요"""
```

**json:**
```json
{
  "pattern_id": "toxic-unpaid_additional_work-01",
  "pattern": "UNPAID_ADDITIONAL_WORK",
  "category": "SCOPE_SOW",
  "title": "추가 업무 지시 시 무상 수행 강요",
  "text": "도급인의 요청에 따라 당초 계약 범위를 초과하는 추가 업무가 발생하더라도 수급인은 이를 별도의 보수 청구 없이 수행하여야 하며, 추가 작업에 소요되는 비용은 수급인이 부담한다."
}
```

---

## 전체 후보 요약

| 항목 | enum 값 | category | enum | json | 출처 |
| --- | --- | --- | --- | --- | --- |
| A-1 | `UNILATERAL_CHANGE` | `SCOPE_SOW` | ✅ | 추가 필요 | 02_converted |
| A-2 | `UNFAIR_DAMAGE_CLAIM` | `LIABILITY` | ✅ | 추가 필요 | 02_converted |
| B-1 | `UNILATERAL_INTERPRETATION` | `DISPUTE` | 추가 필요 | 추가 필요 | data/toxic |
| B-2 | `UNILATERAL_CANCELLATION` | `TERMINATION` | 추가 필요 | 추가 필요 | data/toxic + 02_converted |
| B-3 | `INDEFINITE_CONFIDENTIALITY` | `CONFIDENTIALITY` | 추가 필요 | 추가 필요 | 02_converted |
| B-4 | `UNPAID_ADDITIONAL_WORK` | `SCOPE_SOW` | 추가 필요 | 추가 필요 | 02_converted |
