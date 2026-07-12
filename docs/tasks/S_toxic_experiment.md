# [실험 S] 독소 리랭커 후보 입력에 기존 패턴 제목 보강

> **상태: 승인 대기.** 이 카드는 구현 전 실험 명세다. 승인 전에는 코드, `toxic_patterns.json`,
> 골든셋, 임계값, MCP 계약을 변경하지 않는다.

## 1. 목적과 근거

[R_toxic_error_taxonomy.md](R_toxic_error_taxonomy.md)의 v3/v4 진단 62건 중 현재 v4의 독소 오류는
`LOW_SCORE` FN 16건, `OVER_MATCH` FP 5건이다. 저장된 top-3 후보가 비어 `SEARCH_MISS`로 분류된
사례는 없다. 즉 이번 실험은 검색 후보 수를 늘리거나 임계값을 조정하는 실험이 아니다.

v4 FN 16건의 의미 차원은 `negation` 9건, `authority_subject` 7건이다. 가장 많은 `negation` 축에
대응하되, 새 독소 예문을 추가하지 않고 현재 패턴 레코드가 이미 가진 `title`을 리랭커 입력에 포함해
패턴의 검토 주제를 명시한다.

기준선은 P0/P1에서 동결한 v4 결과다.

| split | toxic threshold | TP | FP | FN | TN | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tuning (36건) | 0.60 | 9 | 5 | 9 | 13 | 0.563 |
| held-out (18건) | 0.60 | 2 | 0 | 7 | 9 | 0.364 |

`v4`는 독소 hard-negative challenge set이다. 이 수치는 검토 패턴 매칭의 실험 기준일 뿐 법적
판정 또는 프로덕션 임계값 변경 근거가 아니다.

## 2. 단일 가설

**가설:** 독소 패턴 후보의 본문만 리랭커에 전달하는 대신, 기존 `title`을 본문 앞에 고정 형식으로
붙이면(예: `검토 패턴: 저작권·지식재산권 전부 무상 귀속\n예문: ...`), 패턴의 핵심 방향을 더 명확히
보여 주어 v4 tuning의 `LOW_SCORE` FN을 줄일 수 있다. 이때 정상 hard-negative에 대한 FP 증가는
허용 한도 안에 머문다.

이 가설은 제목이 현재 코퍼스에 이미 존재하는 결정론적 메타데이터라는 사실에 한정한다. 제목이
부정·기간·권한 주체를 완전하게 해석하거나 법적 결론을 제공한다고 주장하지 않는다.

## 3. 승인 요청 대상: 변경 하나

### 변경 대상 — 리랭커 입력

독소 컬렉션의 검색 결과 중 리랭커에 전달할 **후보 텍스트 하나만** 아래 형식으로 재구성한다.

```text
검토 패턴: {title}
예문: {text}
```

- 사용자 조항 query는 변경하지 않는다.
- dense/BM25 검색 질의, 검색 후보 수(`toxic_top_k=3`), RRF 가중치, 리랭커 모델, 임계값
  (`toxic_threshold=0.60`)은 변경하지 않는다.
- `pattern`, `pattern_id`, `category`, 원본 `text`는 보존한다. 진단 출력에서 원본 후보 본문을
  잃지 않도록, 리랭킹 전 복사본에만 재구성 텍스트를 사용한다.
- `review_contract` 런타임과 `eval.run_eval`의 독소 재정렬이 같은 보조 함수를 사용해야 한다.
  두 경로의 입력 차이로 평가 근거가 달라지는 것을 금지한다.

예상 수정 범위는 `src/core/toxic.py`의 순수 텍스트 조립 함수와 이를 호출하는
`src/pipe/review_pipe.py`, `src/eval/run_eval.py`, 관련 테스트다. 이는 동결된 `DeviationResult` 및
MCP 시그니처를 변경하지 않는다.

### 명시적 비범위

- `data/03_normalized/toxic_patterns.json`의 90개 패턴 예문 추가·삭제·수정
- 새 `ToxicPattern` enum 또는 category 변경
- 검색 후보 수·검색 방식·임계값 스윕을 통한 채택
- v4 골든, held-out manifest, snapshot 변경
- LLM 호출 또는 법적 유불리 판단 생성

## 4. 실험 절차

1. 기준선 커밋과 v4 snapshot/held-out manifest가 일치하는지 확인한다.
2. 순수 함수 테스트를 먼저 추가한다. 제목·본문이 있는 후보는 고정 형식으로 조립하고, 제목 또는
   본문이 없을 때는 조용히 빈 문자열을 만들지 않고 원본 텍스트를 보존한다.
3. 리랭커에 전달되는 독소 후보만 복사·보강한다. 표준조항/서브청크 리랭커 입력은 변경하지 않는다.
4. `just build-db`로 동일 90건 독소 코퍼스를 재색인하고 `just eval a v4 prod`를 **tuning 결과만
   먼저** 읽는다. held-out 결과는 tuning 선택 기준을 통과하기 전까지 열람·해석하지 않는다.
5. tuning 통과 시에만 동결된 held-out으로 한 번 실행한다. 같은 변경을 held-out 결과에 맞춰 수정하거나
   재실행 변형을 추가하지 않는다.
6. 결과와 기존 기준선을 별도 실험 보고서에 기록한다. 기존 `v4_result.md`와 진단 파일은 채택 결정
   전 기준선으로 덮어쓰지 않는다.

## 5. v4 tuning 선택 기준

선택은 기본 `toxic_threshold=0.60`의 tuning 36건만으로 한다. 다른 threshold의 최고 F1을 선택하거나
프로덕션 기본값을 바꾸지 않는다.

다음 **모두**를 만족해야 held-out 단회 검증으로 진행한다.

| 항목 | 기준선 | 통과 기준 |
| --- | ---: | --- |
| FN | 9 | 7 이하 (최소 2건 감소) |
| FP | 5 | 5 이하 (증가 없음) |
| F1 | 0.563 | 0.563 초과 |
| 실행 정합성 | — | 실제 `review_contract` 중 수집한 toxic top-3와 최종 패턴이 일치 |

이 기준은 tuning에서 recall만 올리고 hard-negative를 더 많이 오탐하는 변경을 걸러 내기 위한 것이다.
v3은 채택 선택에 쓰지 않으며, 결과 보고 시 회귀 관찰값으로만 함께 기록한다.

## 6. 동결된 v4 held-out 단회 검증 기준

held-out은 `threshold_heldout.v4.json`의 18 case ID를 그대로 사용하며, 입력·split·snapshot을 수정하지
않는다. tuning 통과 후 단 한 번의 사전 정의된 평가를 수행한다.

| 항목 | 기준선 | 채택 기준 |
| --- | ---: | --- |
| FN | 7 | 6 이하 (최소 1건 감소) |
| FP | 0 | 1 이하 (최대 1건 증가 허용) |
| F1 | 0.364 | 0.364 초과 |
| threshold | 0.60 | 변경 없음 |

FP 허용 한도는 held-out 정상 사례 9건 중 최대 한 사례다. 이는 FN 개선 가능성을 확인하되, 현재의
hard-negative 보호 성질을 크게 훼손하는 변경을 채택하지 않기 위한 상한이다.

## 7. 중단·보류 조건

다음 중 하나라도 발생하면 이 카드에서 추가 변형을 만들지 않고 결과를 `보류` 또는 `폐기`로 기록한다.

1. tuning에서 FN 2건 감소·FP 비증가·F1 개선을 모두 달성하지 못함.
2. held-out에서 FN이 줄지 않거나 FP가 2건 이상으로 증가함.
3. held-out 결과를 본 뒤 제목 형식, 후보 수, threshold, 패턴 예문을 조정하려는 요구가 발생함.
4. MCP/`DeviationResult` 계약 변경, 새 패턴 enum, 법적 판단 문구가 필요해짐.
5. 리랭커 입력 보강 때문에 원본 후보 텍스트·pattern ID·점수 출처를 진단에서 추적할 수 없게 됨.

중단 후 다음 가설은 새 작업 카드와 새 사인오프로만 시작한다. 특히 패턴 예문 증식·확장은 이 실험의
실패를 근거로 자동 승인되지 않는다.

## 8. 구현 완료 조건

- 제목 보강 함수의 정상·누락 필드·원본 불변성 테스트가 추가된다.
- 런타임과 eval 독소 리랭킹 경로가 동일 함수를 사용한다.
- 전체 비통합 테스트가 통과한다.
- tuning 결과, held-out 단회 결과, case-level toxic top-3 diff를 실험 보고서에 남긴다.
- 최종 상태를 `채택`, `보류`, `폐기` 중 하나로 기록한다.
- 채택되어도 프로덕션 `toxic_threshold=0.60`은 별도 승인 없이는 변경하지 않는다.

## 9. 승인 체크리스트

아래 항목을 모두 승인하면 후속 구현 카드가 이 명세의 범위에서만 작업할 수 있다.

- [ ] 독소 후보의 **리랭커 입력에 기존 `title`을 접두**하는 코드 변경을 승인한다.
- [ ] 90건 `toxic_patterns.json`과 `ToxicPattern` enum은 변경하지 않는 데 동의한다.
- [ ] v4 tuning 기준(FN 2건 이상 감소, FP 증가 없음, F1 개선)을 승인한다.
- [ ] 동결 held-out 단회 검증 기준(FN 1건 이상 감소, FP 최대 1건 증가)을 승인한다.
- [ ] held-out 실패 시 추가 조정 없이 보류/폐기하고, 새 실험은 별도 사인오프로 분리하는 데 동의한다.

승인 기록: 담당자 __________ / 승인일 __________ / 승인 범위 __________

## 참고

- [R_toxic_error_taxonomy.md](R_toxic_error_taxonomy.md) — 오류 62건의 재현 가능한 분류
- [N_toxic_corpus_bias.md](N_toxic_corpus_bias.md) — 90건 패턴셋 확장 이력과 변경 제한
- [v4_result.md](../../src/eval/golden/v4_result.md) — 동결 기준선
- [threshold_heldout.v4.json](../../src/eval/golden/threshold_heldout.v4.json) — held-out case ID
- [eval README](../../src/eval/README.md) — 결정론적 지표와 held-out 규칙
