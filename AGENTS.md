# WorkShield 작업 규칙

## 제품 경계

- 1차 MCP는 표준 대비 **검토 후보**를 결정론적으로 검색·매칭·분류한다.
- 1차 코드(`src/contracts`, `src/core`, `src/adapter`, `src/pipe`, `src/server`)에 LLM 호출을 넣지 않는다.
- 2차 LLM은 서버 밖 `demo/` 또는 클라이언트에서만 사용한다.
- 사용자 표면에는 위법·합법·승소·불리함을 단정하지 않는다.

## 계약과 구조

- `src/contracts/`의 enum·Pydantic 모델·port는 동결 계약이다. 변경 전 사람 승인을 받는다.
- `core`는 adapter·외부 I/O를 import하지 않는다. 외부 작업은 port 또는 인자로 주입한다.
- 매칭 실패는 빈 응답으로 숨기지 않고 `NO_MATCH` 등 명시 상태를 반환한다.
- enum 값은 문자열 리터럴 대신 enum으로 사용한다.

## 품질

- 1차 평가는 결정론적 계산만 사용한다. LLM-judge는 사용하지 않는다.
- 활성 회귀 기준은 v5이며, 추가 튜닝·기존 held-out 재실행은 금지한다.
- 새 1차 실험은 새 독립 데이터, 단일 가설, 사전 승인, 독립 held-out이 있을 때만 시작한다.
- 새 로직은 관련 테스트를 먼저 읽고 추가·수정한다.

## 구현 규칙

- 타입힌트와 Pydantic 모델을 사용하고 주석·docstring은 한국어로 작성한다.
- 외부 I/O는 조용히 실패하지 않는다. 빈 값 대신 명시 상태 또는 예외를 사용한다.
- 로컬 경로 문제를 해결하려고 코드에 `sys.path`를 삽입하지 않는다.
- 데이터 원천은 `data/03_normalized`와 migration SQL이며 SQLite·Chroma는 재생성물이다.

## 검증

```bash
just test unit
just test all
just build-db
just docker-build
```

현재 상태는 [docs/START_HERE.md](docs/START_HERE.md), 구조는 [docs/architecture.md](docs/architecture.md)를
참조한다. 세부 작업 이력은 archive 문서이며 현행 명세가 아니다.
