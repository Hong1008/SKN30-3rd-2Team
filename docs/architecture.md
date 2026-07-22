# WorkShield 아키텍처

## 경계

1차 MCP는 LLM 없이 표준 대비 검토 후보를 반환한다. 2차 LLM은 데모/클라이언트가 1차 결과를 받아
의미 차이와 추가 조항을 설명하는 별도 계층이다.

```text
contracts  ← 동결 enum · 모델 · port
   ↑   ↑
core    adapter  ← 순수 판정 / DB·검색·문서·법령 I/O
   ↑   ↑
     pipe        ← 런타임 조립·오프라인 코퍼스 빌드
       ↑
     server      ← FastMCP 표면
       ↑
  외부 client    ← 선택적 2차 LLM과 사용자 경험
```

## 1차 흐름

```text
계약서 → kordoc 파싱 → 조항 분리 → hybrid 검색 → rerank
       ├─ 표준조항 경로 → NONE / EXTRA / NO_MATCH → 전체 표준과 대조 → MISSING
       └─ 독소패턴 경로 → ToxicPattern 0개 이상
       → review_contract_candidates
          ├─ clause_results: NONE / EXTRA / NO_MATCH
          └─ missing_standard_clauses: MISSING 표준조항 후보

필요한 경우: category + contract_type → get_grounding → 관련 법령 원문
```

- `NONE`은 표준 조항과의 1차 잠정 매칭이다.
- `EXTRA`는 근접 후보가 있더라도 점수가 임계값에 못 미친 조항이다.
- `NO_MATCH`는 검색 후보 자체가 없는 명시 상태다.
- `MISSING`은 사용자 계약 전체에서 대응되지 않은 표준 조항이다.

`Deviation`과 `ToxicPattern`은 서로 대체하는 단일 판정 enum이 아니라 독립된 두 축이다. 따라서 사용자
조항은 `NONE`, `EXTRA` 또는 `NO_MATCH`이면서 동시에 `toxic_patterns`를 가질 수 있다. 독소 경로는 알려진
예문과의 유사성을 이용한 보조 검토 신호이며 위법·불공정 여부를 확정하지 않는다. `toxic_patterns=[]`도
독소가 없다는 결론이 아니라 현재 검색에서 임계값 이상의 신호를 찾지 못했다는 뜻이다. MCP를 사용하는
2차 LLM 클라이언트는 이 두 축을 합치거나 `EXTRA`를 독소로 간주하지 않고 각각의 근거로 설명해야 한다.

신규 클라이언트의 기본 경로인 `review_contract_candidates`는 법령을 조회하거나 `grounding`을
노출하지 않는다. 내부 `DeviationResult`는 서버 전용 mapper에서 공개 DTO로 변환하며, 사용자 조항
결과와 `MISSING` 표준조항을 서로 다른 배열로 반환한다.

호환 도구 `review_contract`도 모든 조항의 법령을 조회하지 않는다. 정적 법령 근거는 `MISSING` 중 매핑이
있는 카테고리에만 조건부로 부착되며, `NONE`·`EXTRA`·`NO_MATCH`는 `grounding=[]`을 반환한다.
특정 결과의 법령 원문이 필요하면 클라이언트가 `matched_standard.category`와 `contract_type`으로
`get_grounding`을 별도 호출한다. 표준조항 원문은 두 검토 응답에 이미 포함되므로 일반 검토 흐름에서
`standard://...` 리소스를 다시 읽지 않는다.

## 데이터와 배포

`data/03_normalized`와 migration SQL이 원천이다. SQLite와 Chroma는 `just build-db`로 재생성한다.
운영 Docker 배포는 MCP 단일 컨테이너이며, 임베딩·rerank는 RunPod worker를 사용한다. `demo/`는 배포
대상이 아닌 deprecated된 과거 시연 소스다.

현재 상태·동결 기준선·실행 명령은 [START_HERE](START_HERE.md)를, MCP 도구 상세는
[`src/server/server.py`](../src/server/server.py)를 참조한다.
