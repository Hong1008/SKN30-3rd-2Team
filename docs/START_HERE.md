# WorkShield 현재 상태

WorkShield는 사용자 계약서를 표준계약서와 조항 단위로 대조해 **표준 대비 검토 후보**를 반환하는 MCP
서비스다. 1차는 결정론적 검색·매칭·분류만 수행하며, 법률 해석이나 LLM 호출을 하지 않는다.

## 1차와 2차 경계

- **1차 MCP:** `MISSING` / `EXTRA` / `NONE` / `NO_MATCH` 신호, 대응 표준조항과 독소 패턴을 반환한다. 법령 근거는 일부 `MISSING`에만 조건부로 붙으며 필요하면 `get_grounding`으로 별도 조회한다.
- **선택적 외부 클라이언트:** 필요할 때 `NONE`과 `EXTRA`를 입력으로 LLM이 의미 차이 또는 추가 조항을 설명할 수 있다. 서버 코드에는 LLM을 넣지 않는다.

## 동결된 기준선

- 활성 품질 기준은 v5 조항 골든 135건(SI·SM·SW 각 45건)이다.
- 기본값은 `match_threshold=0.50`, `toxic_threshold=0.60`이다.
- 독소 제목 접두 실험 S는 tuning 실패로 **폐기**했다.
- SW OVER_MATCH 규칙 C1은 held-out에서 FP 기준을 넘겨 **보류**했다.
- 1차 임계값·검색·독소 패턴의 추가 튜닝은 종료한다. 새 독립 데이터와 사전 승인된 가설이 있을 때만 재개한다.

## 현재 작업

현재 활성 개발 작업은 없다. 1차 MCP는 외부 클라이언트가 `review_contract`, `get_grounding`,
표준조항 리소스를 조합해 사용할 수 있는 상태로 완료·동결돼 있다. LLM을 사용하는 별도 클라이언트는
선택 사항이며, 그 연동 원칙은 [선택적 2차 클라이언트 연동 지침](archive/tasks/K_second_stage_llm.md)을
참고한다. 이 지침은 특정 provider·모델·출력 스키마·UI 구현을 요구하지 않는다.

## 자주 쓰는 명령

```bash
just build-db       # SQLite·Chroma 재생성
just test unit      # 결정론적 단위 테스트
just run-mcp        # MCP 서버 실행
just docker-build   # 운영 이미지 빌드
```

자세한 구조는 [architecture.md](architecture.md), 동결 수치는 [quality/baseline-v5.md](quality/baseline-v5.md),
날짜별 근거는 [decisions](decisions)에서 확인한다.
