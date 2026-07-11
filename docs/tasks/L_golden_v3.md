# [재설계 L] 골든셋 v3 — 조 전체 단위 재제작 (SI·SM 확장)

> 근거: [v1_review.md](../../src/eval/golden/v1_review.md) §6·§8.3(최우선 미이행 항목), [07-03 결정 로그](../dicision/07-03.md).
> 선행: 없음(J·K와 독립적으로 진행 가능 — 07-07 세션에서 "골든 스키마 변경 없음" 확정됨).

## 배경

v2 골든셋은 NONE 라벨 44건 중 35건(80%)이 60~90자 단문 `user_clause`를 다항(2개 이상 서브청크)
표준조항에 매핑해, 커버리지 게이트가 구조적으로 NONE에 도달할 수 없는 상태였다(07-03 §1 실측).
v1_review §6 체크리스트 최우선 항목("user_clause를 조 전체 텍스트로")이 v2 제작에서 이행되지
않은 게 근본 원인. 이 카드는 그 이행 — SW_FREELANCE 파일럿(17건, 아래 §완료분)은 이미 있고,
SI_SUBCONTRACT·SM_SUBCONTRACT 확장이 남았다.

## 현재 상태

> **현재 판정: v3 완료.** 아래 SW 파일럿·SI/SM 미착수 표기는 제작 중간 이력이며,
> 2026-07-10에 SI 45·SM 45·SW 27, 총 117건과 39건 held-out manifest를 확정했다.

- ✅ **검증 스크립트 완성**: [validate_golden.py](../../src/eval/golden/validate_golden.py) — 6종 스키마
  검사(gold_toxic 타입/enum, gold_deviation enum, gold_clause_id 코퍼스존재, paraphrase+NONE 금지,
  case_id 중복). `uv run python src/eval/golden/validate_golden.py v3` 로 실행.
- ✅ **SW_FREELANCE 파일럿 17건** ([v3_sw_freelance.json](../../src/eval/golden/v3_sw_freelance.json)) —
  검증 통과. 단항/다항 조항 NONE, 커버리지형·치명변경형(부정어·숫자·당사자) CHANGED, contradiction
  (규칙탐지 불가 케이스 명시적으로 포함 — `v3-sw-11`), reorder(v1·v2 모두 0건이었던 함정 최초 도입,
  `v3-sw-15`), EXTRA 2건.
- ~~SI_SUBCONTRACT·SM_SUBCONTRACT 미착수~~ → ✅ 2026-07-10 완료(아래 완료 기록 참조).

## 07-07 세션에서 확정된 것 — 이 카드에 영향

- `DeviationResult`/골든 스키마에 새 필드 없음(J 카드) → **골든 JSON 포맷은 그대로**, 재작업 불필요.
- 다만 `gold_deviation`의 **채점 의미**가 바뀐다: NONE 라벨은 여전히 "사람이 매긴 진짜 정답"이지만,
  1차(review_contract)만으로는 이제 NONE 여부를 확정할 수 없다(J 카드 참조) — 즉 v3로 1차만
  평가하면 "CHANGED 확정 정확도"만 재는 셈이고, "NONE 정확도"는 K(2차)가 붙어야 온전히 측정
  가능하다. 이건 M 카드 소관이며, **골든 라벨 자체나 제작 방식엔 영향 없음**.

## 구현 대상 (SW 파일럿과 동일 원칙 적용)

1. SI_SUBCONTRACT·SM_SUBCONTRACT 표준 코퍼스(`data/03_normalized/standard_clauses.si_subcontract.*.json`,
   `.sm_subcontract.*.json`)에서 단항/다항 조항을 섞어 표본 선정.
2. 유형별 목표: NONE 15 · CHANGED 15 · EXTRA 5 (유형당 35, 2유형 70건 — SW 17건과 합쳐 v3 전체
   ~87건). trap 분포에 `reorder`를 반드시 포함(v1·v2 모두 0건).
3. NONE 케이스는 표준 원문을 **서식만** 바꿔 복제 — ①②를 1./2.로 바꿀 때 **3개 미만 항목이면
   splitter 임계값 미달로 조 전체가 단일 청크로 남아 중간 숫자가 안 지워지는 함정** 주의
   (`v3-sw-05` 노트 참조, 실측 발견).
4. CHANGED 케이스는 커버리지형(항 삭제)과 의미반전형(규칙탐지 불가, `v3-sw-11`처럼 명시)을 섞는다.
   **문구를 현재 코드가 잡기 쉽게 순화하지 않는다** — 현실적인 말바꿈을 그대로 쓰고, 코드가 못
   잡으면 그 사실을 note에 남긴다(07-07 세션에서 사용자가 지적한 과적합 방지 원칙).
5. 각 케이스 작성 후 즉시 `uv run python src/eval/golden/validate_golden.py v3`로 스키마 검증
   (0건 위반까지).
6. SW 파일럿처럼 `core.calculate_text_similarity`/`detect_critical_changes` **(단, J 완료 후엔
   이 함수 자체가 삭제되므로, J 이후 작성분은 이 사전 검증 단계를 생략하고 커버리지 계산만으로
   sanity-check)** 로 의도한 라벨과 실제 코드 동작이 어긋나지 않는지 1차 점검.

## 2026-07-10 — 임계값 보정용 held-out 확정

- 동결된 골든 케이스 스키마에는 필드를 추가하지 않고,
  [threshold_heldout.v3.json](../../src/eval/golden/threshold_heldout.v3.json)에 case_id 목록을 별도로
  보관한다.
- held-out은 39건(SI 15·SM 15·SW 9), tuning은 78건이다. 각 계약유형의 held-out에는 이탈 양성과
  독소 양성이 최소 2건씩 포함되도록 고정했다.
- `run_eval.py`는 전체합산 표와 함께 tuning·held-out 각각의 `match_threshold`·`toxic_threshold`
  스윕을 출력한다. tuning에서 후보를 고르고, held-out으로만 채택 여부를 확인한다.

### 2026-07-10 — v3 완료 기록

- v3 골든은 SI 45·SM 45·SW 27, 총 117건으로 확정됐고 `validate_golden.py v3` 위반 0건을 확인했다.
- SI/SM은 2025 활성 표준판 기준이며, 각 파일에 `reorder` trap이 포함된다.
- held-out 결과에서 `match_threshold=0.45`는 현재 0.50보다 개선을 재현하지 못했고, 독소 0.75도
  tuning 우세가 held-out에서 재현되지 않았다. 골든 규모 확대·case-level 진단 후에만 새 기본값을
  채택한다.

## 미결정 / 사인오프 필요

- [x] v3 범위 완료. 독소 양성 held-out 확대는 v3 수정이 아니라 **v4 별도 후속**으로 분리
- [x] SI_SUBCONTRACT 기준 표준 — 2025 최신판 고정(Q 카드, 2026-07-10)
- [x] held-out/tuning split — 별도 manifest로 고정(2026-07-10), 골든 JSON 스키마는 불변

## 완료 조건 (DoD)

- [x] `v3_si_subcontract.json`·`v3_sm_subcontract.json` 작성 — 유형당 45건
- [x] `validate_golden.py v3` 전 파일 위반 0건
- [x] trap 분포에 `reorder` 포함 확인
- [x] `gold_clause_id`에 `{contract_type}-{version}-art{N}` 규약 사용

## 참고
- [src/eval/golden/v3_sw_freelance.json](../../src/eval/golden/v3_sw_freelance.json) — 파일럿 17건(형식 참고용)
- [validate_golden.py](../../src/eval/golden/validate_golden.py) · [v1_review.md](../../src/eval/golden/v1_review.md) §6·§8.3
- 후속: [M_eval_dual_track.md](M_eval_dual_track.md) — 이 골든셋으로 무엇을 채점할지 재정의
