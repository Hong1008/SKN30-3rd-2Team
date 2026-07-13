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
  demo/client    ← 2차 LLM과 사용자 경험
```

## 1차 흐름

```text
계약서 → kordoc 파싱 → 조항 분리 → hybrid 검색 → rerank
       → NONE / EXTRA / NO_MATCH → 전체 표준과 대조 → MISSING
       → 독소 신호·법령 근거 → MCP 응답
```

- `NONE`은 표준 조항과의 1차 잠정 매칭이다.
- `EXTRA`는 근접 후보가 있더라도 점수가 임계값에 못 미친 조항이다.
- `NO_MATCH`는 검색 후보 자체가 없는 명시 상태다.
- `MISSING`은 사용자 계약 전체에서 대응되지 않은 표준 조항이다.

## 데이터와 배포

`data/03_normalized`와 migration SQL이 원천이다. SQLite와 Chroma는 `just build-db`로 재생성한다.
MCP와 Streamlit demo는 별도 컨테이너이며, 운영 환경의 임베딩·rerank는 RunPod worker를 사용한다.

현재 상태·동결 기준선·실행 명령은 [START_HERE](START_HERE.md)를, MCP 도구 상세는
[`src/server/server.py`](../src/server/server.py)를 참조한다.
