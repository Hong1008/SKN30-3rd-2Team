# [재설계 P] 검색·리랭킹 입력 텍스트 정규화 — 마크다운 헤더/특수문자 비대칭

> 근거: [07-09 결정 로그](../dicision/07-09.md) — N 카드(독소 코퍼스 이중화) 구현 후 `v3_result.md`
> 재검증 중 실측 발견.
> 선행: 없음. **N_toxic_corpus_bias.md와 독립**(N은 코퍼스 어휘 내용 문제, P는 입력 포맷 문제 — 서로
> 다른 축의 원인이 같은 증상(독소 recall 붕괴)에 겹쳐 있었다).
> ~~이 카드는 질문 목록만 정리 — 해결책은 착수 세션이 결정.~~ **착수 완료(같은 날 후속 세션)**:
> 방향 확정 + 구현까지 마쳤고, recall/F1 재검증(재인덱싱·`just eval`)만 남았다 — 아래 체크리스트 참고.

## 배경 (07-09 실측 요약)

N 카드로 `toxic_patterns.json`에 하도급 어휘(원사업자/수급사업자) 40건 + `INDEFINITE_CONFIDENTIALITY`
10건을 추가하고 `just build-db`로 재인덱싱까지 마쳤으나, 사용자가 실행한 `v3_result.md` 재평가에서
SI/SM 독소 recall이 여전히 0(TP=0)으로 전혀 개선되지 않았다. 원인을 실측한 결과, N 카드가 다룬
"당사자 어휘 편중"과는 **완전히 다른 축의 버그**가 함께 작동하고 있었다:

- 골든셋 `user_clause`는 전부 `"### 제43조(경업금지 및 인력 유출 방지)\n본문..."`처럼 **마크다운 조항
  헤더가 붙은 형태**다(`v3_si_subcontract.json`·`v3_sm_subcontract.json`·`v3_sw_freelance.json` 공통).
  `review_contract`는 이 헤더 포함 원문을 그대로 검색·리랭킹 쿼리로 사용한다.
- `data/03_normalized/standard_clauses.*.json`(표준조항 코퍼스)도 동일하게 `"### 제1조(목적) ..."`
  형태로 헤더가 붙어 있다 — 쿼리·문서 양쪽이 **대칭**이라 표준조항 매칭(이탈 탐지)은 이 문제가 없다
  (`v3_result.md`의 이탈 F1이 정상인 이유).
- 반면 `data/03_normalized/toxic_patterns.json`(독소 코퍼스, 90건 — 기존 40건 포함 전부)은 헤더 없는
  **평문 문장**으로만 작성돼 있다. 쿼리(헤더 있음) vs 독소 코퍼스 문서(헤더 없음)의 **비대칭**이
  크로스인코더(`bge-reranker-v2-m3-ko`) 점수를 붕괴시킨다.

### 재현 데이터 (동일 문서쌍, 쿼리의 헤더 유무만 다름)

| 계약유형 | 케이스 | 헤더 포함 쿼리 리랭크 점수 | 헤더 제거(본문만) 리랭크 점수 |
| --- | --- | --- | --- |
| SI_SUBCONTRACT | v3-si-31 (`NONCOMPETE_EXCESS`) | 0.00036 | 0.9979 |
| SW_FREELANCE | v3-sw-07 (`INDEFINITE_CONFIDENTIALITY`) | 0.009 | 0.9999 |

`toxic_threshold=0.6` 기준으로 헤더 포함 쿼리는 사실상 항상 미달 — SI/SM뿐 아니라 SW의 낮은 독소
recall(0.333)도 이 비대칭의 영향을 받았을 가능성이 높다(코퍼스 개선 이전부터 존재하던, 세 계약유형
공통의 근본 원인).

## 문제 정의 (해결책 아님 — 착수 세션이 설계할 것)

리랭커는 쿼리·문서 두 텍스트의 **표면 형식이 다르면**(한쪽엔 조 번호·제목이, 다른 쪽엔 없으면) 내용이
동일해도 무관하다고 판단한다. 독소 검색은 코퍼스 문서에 "조항 정체성"(제N조·제목)이 애초에 없는
자유 예문이라 이 비대칭이 구조적으로 발생한다.

## 검토할 방향 (07-09에서 거론 — 순위·선택은 착수 세션 몫)

사용자가 "이번 기회에 데이터 정규화를 전반적으로 검토해야 한다"고 제기 — 국소 패치(독소 쿼리에서만
헤더 제거)보다 넓은 범위를 시사:

1. **국소 패치**: `review_pipe.py`의 독소 역방향 검색 단계에서만 쿼리 텍스트의 헤더(`"### 제N조(...)"`
   또는 `"제N조(...)"` 패턴)를 제거하고 독소 컬렉션 검색·리랭킹에 투입. 표준/서브청크 검색용
   `clause_vectors`·원본 텍스트는 그대로 둔다(그쪽은 대칭이라 안전).
2. **DB 저장 데이터 전반 정규화**: `data/03_normalized/*.json`에 적재되는 텍스트(표준조항·서브청크·
   독소패턴)에서 마크다운 헤더·특수문자를 일관되게 제거하거나, 반대로 독소 코퍼스에도 표준조항과
   동일한 헤더 형식을 부여해 대칭을 맞춘다.
3. **사용자 입력 정규화 공유**: 사용자 계약서 조항(`Clause.text`)이 파싱(split)된 이후 동일한 정규화
   과정을 거치도록 해, corpus 적재 시점과 런타임 쿼리 시점의 정규화 로직을 **하나로 공유**한다(지금은
   결과가 겹치는 별개 지점에서 각자 다르게 처리될 여지가 있음 — 공유 정규화 함수 필요 여부 확인).

## 미결정 / 사인오프 필요 (AGENTS.md §2)

- [x] 방향 1(국소 패치) vs 방향 2·3(전면 정규화) 중 범위 — **제3의 범위로 확정**: `standard_clauses`·
      `standard_sub_chunks`·`toxic_patterns` JSON(`03_normalized`)과 골든셋 파일은 **원본 그대로 두고**,
      임베딩·BM25 색인에 들어가는 텍스트만 색인 직전에 정규화하는 방식으로 결정. `pipe/normalize.py`
      (03_normalized 생성 로직)·`kordoc` 파싱은 변경하지 않았다 — "동결 데이터 재생성 범위"를 건드리는
      전면 정규화(방향 2)는 채택하지 않음.
- [x] 정규화를 어느 레이어에 둘지 — **(c) 공유 함수 + 두 호출부**로 결정·구현: 순수 함수
      `normalize_for_search`를 [core/splitter.py](../../src/core/splitter.py)에 추가(기존 항·호 정규식과
      한 파일에서 공유)하고, 오프라인 [pipe/build_index.py](../../src/pipe/build_index.py)(Chroma upsert
      직전 `documents`)·런타임 [pipe/review_pipe.py](../../src/pipe/review_pipe.py)(`clause_texts`) 두
      지점에서 호출. BM25 코퍼스·쿼리도 이 두 텍스트를 그대로 재사용하므로(`vector_manager.py`가 Chroma
      `documents`를 그대로 읽어 BM25 색인을 만듦) 별도 배선 없이 dense·BM25 양쪽에 동시 적용됨.
  - **표준조항 쪽 ablation은 아직 미실행** — 아래 DoD "표준조항 F1 회귀 확인" 항목 참고(재인덱싱 필요).
- [x] "특수문자 제거"의 구체 범위 — **좁게 확정**: 마크다운 헤더(`#`, `제N조(제목)`의 조번호·괄호)와
      항·호 열거기호(`①~⑳`·`1.`·`1)`·`- 1)`)만 제거 대상으로 한정. 제목 텍스트·본문의 실제 숫자
      (계약기간·금액 등)·기타 구두점은 보존(테스트로 확정:
      [tests/core/test_splitter.py](../../tests/core/test_splitter.py)의 `test_본문_숫자는_보존` 등).
      `core/splitter.py`의 기존 항·호 정규식(`_SYMBOL_RE`·`_NUM_RE`·`_SPLIT_RE`)과 같은 문자 클래스를
      재사용해 G_sub_chunk.md 분할 로직과의 충돌 없이 정의됨.

## 완료 조건 (DoD)

- [x] 방향 확정 + 구현 — `core/splitter.normalize_for_search` 추가, `build_index.py`·`review_pipe.py`
      배선, `tests/core/test_splitter.py`에 정규화 테스트 8건 추가(102개 전체 테스트 통과, 회귀 없음).
- [x] [N_toxic_corpus_bias.md](N_toxic_corpus_bias.md) DoD의 독소 recall 재측정 — `just build-db`와
      v3 prod eval을 재실행해 TP=8/18까지 회복했으나 SI/SM 격차·precision 문제는 N 후속으로 남음.
- [x] 표준조항 이탈·검색 지표 재확인 — Q 활성코퍼스 적용 뒤 A-1 hybrid Recall@5=0.920·MRR=0.903.
      A-2의 잔여 FN은 P 회귀가 아니라 Q 후에도 남는 매칭 경계 사례로 분리했다.
- [x] LLM 없이 규칙 기반 정규화만(규칙 #1), 지표는 결정론(규칙 #5) — `normalize_for_search`는 순수
      정규식 함수(LLM 호출 없음), `run_eval.py` 지표 코드는 변경하지 않아 결정론 그대로 유지.

## 참고
- [07-09 결정 로그](../dicision/07-09.md) — 재현 데이터·실측 경위
- [src/pipe/review_pipe.py](../../src/pipe/review_pipe.py) — `TOXIC_COLLECTION` 검색·리랭킹 지점
- [src/pipe/normalize.py](../../src/pipe/normalize.py) — 03_normalized 생성 로직
- [data/03_normalized/toxic_patterns.json](../../data/03_normalized/toxic_patterns.json) ·
  [standard_clauses.*.json](../../data/03_normalized/) — 헤더 비대칭 비교 대상
