# WorkShield 현재 상태

WorkShield는 사용자 계약서를 표준계약서와 조항 단위로 대조해 **표준 대비 검토 후보**를 반환하는 MCP
서비스다. 1차는 결정론적 검색·매칭·분류만 수행하며, 법률 해석이나 LLM 호출을 하지 않는다.

## 1차와 2차 경계

- **1차 MCP:** `MISSING` / `EXTRA` / `NONE` / `NO_MATCH` 신호, 대응 표준조항, 독소 패턴, 근거 자료를 반환한다.
- **2차 클라이언트/데모:** `NONE`과 `EXTRA`를 입력으로 LLM이 의미 차이 또는 추가 조항을 설명한다. 서버 코드에는 LLM을 넣지 않는다.

## 동결된 기준선

- 활성 품질 기준은 v5 조항 골든 135건(SI·SM·SW 각 45건)이다.
- 기본값은 `match_threshold=0.50`, `toxic_threshold=0.60`이다.
- 독소 제목 접두 실험 S는 tuning 실패로 **폐기**했다.
- SW OVER_MATCH 규칙 C1은 held-out에서 FP 기준을 넘겨 **보류**했다.
- 1차 임계값·검색·독소 패턴의 추가 튜닝은 종료한다. 새 독립 데이터와 사전 승인된 가설이 있을 때만 재개한다.

## 현재 작업

[K — 2차 LLM 제품화](roadmap.md)가 유일한 활성 작업이다. structured output 스키마와 모델을 승인한 뒤,
데모 레이어에서 1차 MCP 결과를 소비한다.

## 자주 쓰는 명령

```bash
just build-db       # SQLite·Chroma 재생성
just test unit      # 결정론적 단위 테스트
just run-mcp        # MCP 서버 실행
just docker-build   # 운영 이미지 빌드
```

자세한 구조는 [architecture.md](architecture.md), 동결 수치는 [quality/baseline-v5.md](quality/baseline-v5.md),
날짜별 근거는 [decisions](decisions)에서 확인한다.
