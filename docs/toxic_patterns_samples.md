# 독소조항 예시 문장 목록 (json 삽입 후보)

> `data/02_converted/` 계약서 MD 파일의 표준 조항을 역방향으로 추출한 예시 문장.
> enum 확정 후 `data/03_normalized/toxic_patterns.json` 에 삽입한다.
> 패턴당 5문장, 총 9패턴 × 5문장 = 45 엔트리.

---

## IP_TOTAL_FREE — 저작권·지식재산권 전부 무상 귀속

> 근거: 도급계약서 제20조 "수급인과 도급인의 공동소유", 근로계약서 제15조 "저작권법 등에 근로자의 권리를 인정하는 특별한 규정이 있는 경우에는 그에 따른다"

```json
{ "pattern_id": "toxic-ip_total_free-01", "pattern": "IP_TOTAL_FREE", "category": "IP_OWNERSHIP", "title": "저작권·지식재산권 전부 무상 귀속", "text": "본 계약에 따라 발생하는 모든 결과물, 산출물 및 그에 관한 저작권·지식재산권 일체는 별도의 대가 없이 전부 도급인에게 영구적으로 귀속되며, 수급인은 저작인격권을 포함한 어떠한 권리도 주장하지 아니한다." },
{ "pattern_id": "toxic-ip_total_free-02", "pattern": "IP_TOTAL_FREE", "category": "IP_OWNERSHIP", "title": "저작권·지식재산권 전부 무상 귀속", "text": "수급인이 본 계약 수행 중 개발하거나 개선한 소프트웨어, 알고리즘, 기술 노하우 및 이와 관련된 일체의 지식재산권은 계약 체결과 동시에 도급인에게 이전된 것으로 보며, 수급인은 추가적인 보상을 청구할 수 없다." },
{ "pattern_id": "toxic-ip_total_free-03", "pattern": "IP_TOTAL_FREE", "category": "IP_OWNERSHIP", "title": "저작권·지식재산권 전부 무상 귀속", "text": "본 계약의 결과물에 대한 저작권 및 특허권 등 모든 지식재산권은 도급인에게 귀속되고, 수급인이 계약 이전부터 보유하던 기술·도구를 활용한 경우에도 해당 결과물에 관한 권리는 도급인의 소유로 한다." },
{ "pattern_id": "toxic-ip_total_free-04", "pattern": "IP_TOTAL_FREE", "category": "IP_OWNERSHIP", "title": "저작권·지식재산권 전부 무상 귀속", "text": "수급인은 본 계약 업무 수행과 관련하여 창작한 2차적저작물, 편집저작물을 포함한 모든 저작물에 대해 도급인에게 저작재산권 전부를 양도하며, 도급인의 동의 없이 해당 저작물을 어떠한 방법으로도 이용할 수 없다." },
{ "pattern_id": "toxic-ip_total_free-05", "pattern": "IP_TOTAL_FREE", "category": "IP_OWNERSHIP", "title": "저작권·지식재산권 전부 무상 귀속", "text": "수급인은 계약 종료 후에도 도급인이 요청하는 경우 언제든지 본 계약 결과물과 관련된 지식재산권의 이전·등록 절차에 협력하여야 하며, 이에 소요되는 비용은 수급인이 부담한다." }
```

---

## NONCOMPETE_EXCESS — 과도한 경업금지·영업활동 제한

> 근거: 도급계약서 제17조 "비밀 준수 기간은 업무 종료 후 1년" — 경업금지 조항 자체가 없는 것이 표준, 포함되면 독소

```json
{ "pattern_id": "toxic-noncompete_excess-01", "pattern": "NONCOMPETE_EXCESS", "category": "CONFIDENTIALITY", "title": "과도한 경업금지·영업활동 제한", "text": "수급인은 본 계약 종료 후 3년간 도급인과 동종·유사한 업종에 종사하거나 경쟁 업체에 용역을 제공할 수 없으며, 이를 위반할 경우 보수의 5배에 해당하는 위약금을 지급한다." },
{ "pattern_id": "toxic-noncompete_excess-02", "pattern": "NONCOMPETE_EXCESS", "category": "CONFIDENTIALITY", "title": "과도한 경업금지·영업활동 제한", "text": "수급인은 계약 기간 중 및 계약 종료 후 2년간 도급인의 현재 또는 잠재 고객사에 직접 또는 간접으로 동종 용역을 제공하는 일체의 영업 활동을 하지 못한다." },
{ "pattern_id": "toxic-noncompete_excess-03", "pattern": "NONCOMPETE_EXCESS", "category": "CONFIDENTIALITY", "title": "과도한 경업금지·영업활동 제한", "text": "수급인은 계약 종료일로부터 5년간 도급인이 영업 활동을 하는 국내외 전 지역에서 도급인과 경쟁 관계에 있는 업체의 임직원, 자문위원, 프리랜서로 활동할 수 없다." },
{ "pattern_id": "toxic-noncompete_excess-04", "pattern": "NONCOMPETE_EXCESS", "category": "CONFIDENTIALITY", "title": "과도한 경업금지·영업활동 제한", "text": "수급인은 본 계약 종료 후 1년 이내에 도급인의 임직원을 채용하거나 채용을 권유하여서는 아니 되며, 이를 위반한 경우 해당 임직원의 연간 보수에 상당하는 금액을 위약금으로 지급한다." },
{ "pattern_id": "toxic-noncompete_excess-05", "pattern": "NONCOMPETE_EXCESS", "category": "CONFIDENTIALITY", "title": "과도한 경업금지·영업활동 제한", "text": "수급인은 계약 종료 후 3년간 도급인 또는 도급인의 계열사가 수행 중인 프로젝트와 유사한 성격의 프로젝트에 참여하거나 관련 정보를 활용하는 일체의 행위를 금한다." }
```

---

## PAYMENT_DELAY_UNFAIR — 부당한 대금 지급 지연·지체상금 면제

> 근거: 도급계약서 제6조① "지급 기한 초과 시 지체일수마다 1000분의 1.25 지연이자 지급", 제6조④ "귀책사유 없는 불합리한 이유로 보수 감액·연기 불가"

```json
{ "pattern_id": "toxic-payment_delay_unfair-01", "pattern": "PAYMENT_DELAY_UNFAIR", "category": "PAYMENT", "title": "부당한 대금 지급 지연·지체상금 면제", "text": "도급인은 발주자로부터 대금을 수령한 이후에 수급인에게 보수를 지급하며, 지급 시기에 관하여 어떠한 지연이자나 지체상금도 부담하지 아니한다. 도급인의 사정에 따라 지급을 무기한 연기할 수 있다." },
{ "pattern_id": "toxic-payment_delay_unfair-02", "pattern": "PAYMENT_DELAY_UNFAIR", "category": "PAYMENT", "title": "부당한 대금 지급 지연·지체상금 면제", "text": "수급인에 대한 보수 지급은 도급인이 발주자로부터 검수 완료 후 최종 대금을 수령한 날로부터 60일 이내에 하며, 발주자의 지급 지연을 이유로 수급인은 도급인에게 지연이자를 청구할 수 없다." },
{ "pattern_id": "toxic-payment_delay_unfair-03", "pattern": "PAYMENT_DELAY_UNFAIR", "category": "PAYMENT", "title": "부당한 대금 지급 지연·지체상금 면제", "text": "도급인은 프로젝트 최종 완료 및 도급인의 내부 승인 절차 완료 후 보수를 지급하며, 내부 승인 기간은 도급인이 임의로 정할 수 있고 이로 인한 지급 지연에 대해 수급인은 이의를 제기하지 아니한다." },
{ "pattern_id": "toxic-payment_delay_unfair-04", "pattern": "PAYMENT_DELAY_UNFAIR", "category": "PAYMENT", "title": "부당한 대금 지급 지연·지체상금 면제", "text": "수급인의 업무 완료 후 도급인은 품질 검토를 이유로 보수 지급을 유보할 수 있으며, 검토 기간 및 최종 지급 여부는 도급인이 단독으로 결정한다. 이 기간 중 발생하는 지연에 대한 이자는 부담하지 아니한다." },
{ "pattern_id": "toxic-payment_delay_unfair-05", "pattern": "PAYMENT_DELAY_UNFAIR", "category": "PAYMENT", "title": "부당한 대금 지급 지연·지체상금 면제", "text": "도급인은 경영 사정, 자금 유동성 부족 등의 이유로 수급인에 대한 보수 지급을 계약에서 정한 기일보다 최장 120일까지 연장할 수 있으며, 이에 대해 수급인은 지연이자 또는 위약금을 청구할 수 없다." }
```

---

## UNILATERAL_CHANGE — 일방적인 과업 범위 변경 권한

> 근거: 도급계약서 제4조⑤ "서면 합의에 따라서만 변경, 부당 강요 금지", 제4조③ "명시되지 않은 사항 요구 불가", 상용소프트웨어 제11조 "추가작업은 동의 + 추가작업서 필수"

```json
{ "pattern_id": "toxic-unilateral_change-01", "pattern": "UNILATERAL_CHANGE", "category": "SCOPE_SOW", "title": "일방적인 과업 범위 변경 권한", "text": "도급인은 필요에 따라 수급인과의 사전 협의 없이 업무 범위, 납기일, 산출물 규격을 변경할 수 있으며, 수급인은 추가 보수 청구 없이 이에 응하여야 한다." },
{ "pattern_id": "toxic-unilateral_change-02", "pattern": "UNILATERAL_CHANGE", "category": "SCOPE_SOW", "title": "일방적인 과업 범위 변경 권한", "text": "도급인은 프로젝트 진행 중 업무 내용 및 범위를 변경하거나 추가할 수 있으며, 수급인은 변경 또는 추가된 업무가 계약 당초 범위를 초과하더라도 기존 보수 범위 내에서 이를 수행하여야 한다." },
{ "pattern_id": "toxic-unilateral_change-03", "pattern": "UNILATERAL_CHANGE", "category": "SCOPE_SOW", "title": "일방적인 과업 범위 변경 권한", "text": "도급인이 납기일을 단축하거나 업무 우선순위를 변경하는 경우 수급인은 이에 즉시 응하여야 하며, 납기 단축으로 인한 추가 인력 투입 비용 등은 수급인이 부담한다." },
{ "pattern_id": "toxic-unilateral_change-04", "pattern": "UNILATERAL_CHANGE", "category": "SCOPE_SOW", "title": "일방적인 과업 범위 변경 권한", "text": "도급인은 발주자의 요청 또는 내부 사정에 따라 계약 목적물의 기능, 성능, 규격을 계약 후에도 변경할 수 있으며, 수급인은 변경 사항을 통보받은 날로부터 3영업일 이내에 이행 계획을 제출하고 추가 비용 없이 수행한다." },
{ "pattern_id": "toxic-unilateral_change-05", "pattern": "UNILATERAL_CHANGE", "category": "SCOPE_SOW", "title": "일방적인 과업 범위 변경 권한", "text": "계약서에 명시되지 않은 사항이라도 도급인이 업무 범위에 포함되는 것으로 판단하는 경우 수급인은 이를 수행할 의무가 있으며, 이에 대한 별도의 보수는 지급되지 아니한다." }
```

---

## UNFAIR_DAMAGE_CLAIM — 부당하게 과도한 손해배상 청구액 설정

> 근거: 도급계약서 제6조③ "지체일수당 1000분의 1.25 공제"가 표준 기준 — 이를 크게 초과하는 배율이 독소

```json
{ "pattern_id": "toxic-unfair_damage_claim-01", "pattern": "UNFAIR_DAMAGE_CLAIM", "category": "LIABILITY", "title": "부당하게 과도한 손해배상 청구액 설정", "text": "수급인이 납기를 지키지 못하거나 도급인이 요구한 품질 기준을 충족하지 못할 경우, 수급인은 계약 금액 상당액에 해당하는 금액을 손해배상액으로 지급하여야 한다." },
{ "pattern_id": "toxic-unfair_damage_claim-02", "pattern": "UNFAIR_DAMAGE_CLAIM", "category": "LIABILITY", "title": "부당하게 과도한 손해배상 청구액 설정", "text": "납기 지연 시 수급인은 지체 1일당 계약 금액의 1%를 위약금으로 도급인에게 지급하며, 도급인의 입증 없이도 해당 금액을 미지급 보수에서 일방적으로 공제할 수 있다." },
{ "pattern_id": "toxic-unfair_damage_claim-03", "pattern": "UNFAIR_DAMAGE_CLAIM", "category": "LIABILITY", "title": "부당하게 과도한 손해배상 청구액 설정", "text": "수급인의 귀책사유로 인한 하자 발생 시 수급인은 하자 복구 비용 외에 도급인이 입은 간접 손해, 기회손실, 영업상 손해 일체를 배상하여야 하며, 그 금액은 도급인이 산정한 바에 따른다." },
{ "pattern_id": "toxic-unfair_damage_claim-04", "pattern": "UNFAIR_DAMAGE_CLAIM", "category": "LIABILITY", "title": "부당하게 과도한 손해배상 청구액 설정", "text": "수급인이 본 계약을 중도에 해지하거나 계약 이행을 거부하는 경우, 계약 잔여 기간에 해당하는 보수 전액 및 도급인이 대체 용역 수급에 소요한 비용의 합산액을 위약금으로 즉시 지급하여야 한다." },
{ "pattern_id": "toxic-unfair_damage_claim-05", "pattern": "UNFAIR_DAMAGE_CLAIM", "category": "LIABILITY", "title": "부당하게 과도한 손해배상 청구액 설정", "text": "도급인이 산출물의 품질이 계약 목적에 현저히 미달한다고 판단하는 경우, 수급인은 도급인이 산정한 손해액 전부를 배상하여야 하며 이에 대하여 이의를 제기할 수 없다." }
```

---

## UNILATERAL_INTERPRETATION — 발주자의 일방적 계약 해석 권한 ⚠️ enum 추가 필요

> 근거: 도급계약서 제21조 "우선적으로 서면 자료, 상관습, 그래도 해결 안 되면 상호 협의" — 이를 도급인 단독 해석으로 대체하면 독소

```json
{ "pattern_id": "toxic-unilateral_interpretation-01", "pattern": "UNILATERAL_INTERPRETATION", "category": "DISPUTE", "title": "발주자의 일방적 계약 해석 권한", "text": "본 계약 내용에 관하여 당사자 간 이견이 발생할 경우 도급인의 해석 및 판단에 따르며, 수급인은 이에 이의를 제기하지 아니한다." },
{ "pattern_id": "toxic-unilateral_interpretation-02", "pattern": "UNILATERAL_INTERPRETATION", "category": "DISPUTE", "title": "발주자의 일방적 계약 해석 권한", "text": "계약서 조항의 해석에 대한 분쟁이 발생하는 경우 도급인이 최종 해석 권한을 가지며, 수급인은 도급인의 해석에 따라 업무를 이행하여야 한다." },
{ "pattern_id": "toxic-unilateral_interpretation-03", "pattern": "UNILATERAL_INTERPRETATION", "category": "DISPUTE", "title": "발주자의 일방적 계약 해석 권한", "text": "본 계약의 해석상 이견이 발생하는 경우 도급인의 해석을 우선 기준으로 하여 처리하며, 수급인은 이에 따라 업무를 수행하여야 한다." },
{ "pattern_id": "toxic-unilateral_interpretation-04", "pattern": "UNILATERAL_INTERPRETATION", "category": "DISPUTE", "title": "발주자의 일방적 계약 해석 권한", "text": "계약 내용의 모호성이나 누락으로 인한 분쟁 발생 시 도급인의 원래 의도를 기준으로 해석하며, 수급인은 도급인이 제시한 해석을 서면으로 이의 없이 수용한다." },
{ "pattern_id": "toxic-unilateral_interpretation-05", "pattern": "UNILATERAL_INTERPRETATION", "category": "DISPUTE", "title": "발주자의 일방적 계약 해석 권한", "text": "수급인이 특정 조항에 대해 다른 해석을 주장하는 경우에도 도급인의 해석을 우선으로 하며, 수급인은 법적 절차를 제기하기 전에 도급인의 해석에 따라 계약을 이행하여야 한다." }
```

---

## UNILATERAL_CANCELLATION — 발주자의 일방적 위탁 취소 및 무보상 계약 해지 ⚠️ enum 추가 필요

> 근거: 상용소프트웨어 제24조 "귀책사유 없으면 위탁 임의 취소 금지", 도급계약서 제16조③ "합리적 이유 없이 해지 불가, 작업 성과물 대가 지급"

```json
{ "pattern_id": "toxic-unilateral_cancellation-01", "pattern": "UNILATERAL_CANCELLATION", "category": "TERMINATION", "title": "발주자의 일방적 위탁 취소 및 무보상 계약 해지", "text": "도급인은 계약 이행 중이라도 경영상 필요에 따라 본 계약을 해지할 수 있으며, 이 경우 수급인에게 기이행 부분에 대한 보수를 지급하지 아니하고 수급인은 이에 이의를 제기하지 아니한다." },
{ "pattern_id": "toxic-unilateral_cancellation-02", "pattern": "UNILATERAL_CANCELLATION", "category": "TERMINATION", "title": "발주자의 일방적 위탁 취소 및 무보상 계약 해지", "text": "도급인은 프로젝트 방향 변경, 예산 삭감, 발주자 사정 등을 이유로 계약을 즉시 해지할 수 있으며, 이 경우 수급인에 대한 보상은 없고 수급인은 즉시 업무를 중단하여야 한다." },
{ "pattern_id": "toxic-unilateral_cancellation-03", "pattern": "UNILATERAL_CANCELLATION", "category": "TERMINATION", "title": "발주자의 일방적 위탁 취소 및 무보상 계약 해지", "text": "도급인은 수급인의 업무 결과물이 도급인의 내부 기준에 미치지 못한다고 판단하는 경우 서면 통지만으로 계약을 해지할 수 있으며, 기지급된 선급금을 포함하여 수급인은 추가 보상을 청구할 수 없다." },
{ "pattern_id": "toxic-unilateral_cancellation-04", "pattern": "UNILATERAL_CANCELLATION", "category": "TERMINATION", "title": "발주자의 일방적 위탁 취소 및 무보상 계약 해지", "text": "본 계약은 도급인의 사정에 의해 언제든지 해지될 수 있으며, 해지 시 수급인은 진행 중인 업무를 즉시 중단하고 관련 자료를 도급인에게 반환하여야 한다. 수급인은 해지로 인한 손실에 대해 도급인에게 청구권을 행사하지 아니한다." },
{ "pattern_id": "toxic-unilateral_cancellation-05", "pattern": "UNILATERAL_CANCELLATION", "category": "TERMINATION", "title": "발주자의 일방적 위탁 취소 및 무보상 계약 해지", "text": "발주자의 계약 취소 또는 도급인의 내부 결정에 따라 본 계약이 중도 해지되는 경우, 수급인은 해지 통보를 받은 즉시 업무를 종료하여야 하며 미완료 부분에 대한 보수는 지급되지 아니한다." }
```

---

## INDEFINITE_CONFIDENTIALITY — 무기한·과도한 비밀유지 기간 설정 ⚠️ enum 추가 필요

> 근거: 도급계약서 제17조④ "비밀 준수 기간은 업무 종료 후 **1년**" — 이를 무기한·장기간으로 대체하면 독소

```json
{ "pattern_id": "toxic-indefinite_confidentiality-01", "pattern": "INDEFINITE_CONFIDENTIALITY", "category": "CONFIDENTIALITY", "title": "무기한·과도한 비밀유지 기간 설정", "text": "수급인은 본 계약 종료 후에도 기간의 제한 없이 영구적으로 도급인의 영업비밀 및 기술정보 일체를 제3자에게 공개하거나 본인의 영업 목적으로 활용할 수 없으며, 이를 위반할 경우 손해배상 책임을 진다." },
{ "pattern_id": "toxic-indefinite_confidentiality-02", "pattern": "INDEFINITE_CONFIDENTIALITY", "category": "CONFIDENTIALITY", "title": "무기한·과도한 비밀유지 기간 설정", "text": "수급인은 계약 종료 후 10년간 본 계약 업무 수행 중 취득하거나 알게 된 도급인의 기술 정보, 고객 정보, 사업 전략 등 일체의 정보를 외부에 공개하거나 활용할 수 없다." },
{ "pattern_id": "toxic-indefinite_confidentiality-03", "pattern": "INDEFINITE_CONFIDENTIALITY", "category": "CONFIDENTIALITY", "title": "무기한·과도한 비밀유지 기간 설정", "text": "수급인의 비밀유지 의무는 계약 기간 중은 물론 계약 종료 후에도 영구히 존속하며, 도급인이 비밀이라고 지정한 정보뿐만 아니라 업무 수행 과정에서 알게 된 모든 정보에 적용된다." },
{ "pattern_id": "toxic-indefinite_confidentiality-04", "pattern": "INDEFINITE_CONFIDENTIALITY", "category": "CONFIDENTIALITY", "title": "무기한·과도한 비밀유지 기간 설정", "text": "수급인은 계약 종료 후 5년간 도급인의 사전 서면 동의 없이 본 계약과 관련하여 취득한 어떠한 정보도 직접 또는 간접으로 이용하거나 제3자에게 제공할 수 없으며, 이 의무는 해당 정보의 공개 여부와 무관하게 적용된다." },
{ "pattern_id": "toxic-indefinite_confidentiality-05", "pattern": "INDEFINITE_CONFIDENTIALITY", "category": "CONFIDENTIALITY", "title": "무기한·과도한 비밀유지 기간 설정", "text": "수급인은 본 계약 종료 후에도 도급인이 비밀 해제를 서면으로 통보하기 전까지 비밀유지 의무를 부담하며, 도급인은 비밀 해제 시기를 임의로 결정할 수 있다." }
```

---

## UNPAID_ADDITIONAL_WORK — 추가 업무 지시 시 무상 수행 강요 ⚠️ enum 추가 필요

> 근거: 상용소프트웨어 제11조 "추가작업은 동의 + 추가작업서 필수, 발주자 미지급 시에도 원사업자가 수급사업자에게 증액 지급"

```json
{ "pattern_id": "toxic-unpaid_additional_work-01", "pattern": "UNPAID_ADDITIONAL_WORK", "category": "SCOPE_SOW", "title": "추가 업무 지시 시 무상 수행 강요", "text": "도급인의 요청에 따라 당초 계약 범위를 초과하는 추가 업무가 발생하더라도 수급인은 이를 별도의 보수 청구 없이 수행하여야 하며, 추가 작업에 소요되는 비용은 수급인이 부담한다." },
{ "pattern_id": "toxic-unpaid_additional_work-02", "pattern": "UNPAID_ADDITIONAL_WORK", "category": "SCOPE_SOW", "title": "추가 업무 지시 시 무상 수행 강요", "text": "수급인은 도급인의 서면 또는 구두 지시에 따른 추가 작업을 계약에 명시되지 않은 경우에도 수행할 의무가 있으며, 추가 작업에 대한 별도의 대가를 청구할 권리를 포기한다." },
{ "pattern_id": "toxic-unpaid_additional_work-03", "pattern": "UNPAID_ADDITIONAL_WORK", "category": "SCOPE_SOW", "title": "추가 업무 지시 시 무상 수행 강요", "text": "본 계약 범위 외의 업무라도 도급인이 본 계약의 목적 달성에 필요하다고 판단하는 경우, 수급인은 해당 업무를 계약된 보수 내에서 이행하여야 하며, 이에 대한 추가 보수를 청구하지 아니한다." },
{ "pattern_id": "toxic-unpaid_additional_work-04", "pattern": "UNPAID_ADDITIONAL_WORK", "category": "SCOPE_SOW", "title": "추가 업무 지시 시 무상 수행 강요", "text": "프로젝트 완성을 위해 도급인이 요청하는 수정, 보완, 추가 기능 구현 등의 작업은 검수 완료 전까지 수급인의 의무 범위에 포함되며, 추가 비용이 발생하더라도 도급인에게 청구할 수 없다." },
{ "pattern_id": "toxic-unpaid_additional_work-05", "pattern": "UNPAID_ADDITIONAL_WORK", "category": "SCOPE_SOW", "title": "추가 업무 지시 시 무상 수행 강요", "text": "발주자 또는 도급인의 요구 사항 변경에 따라 수급인이 수행하는 추가 작업 및 재작업에 대해 도급인은 별도의 대가를 지급하지 아니하며, 수급인은 이를 납품 의무의 일환으로 수행한다." }
```
