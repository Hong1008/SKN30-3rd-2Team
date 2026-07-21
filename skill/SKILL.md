---
name: workshield-mcp
description: WorkShield MCP로 IT·SW 계약서를 표준계약서와 결정론적으로 비교하고 표준조항·법령 원문을 조회한다. WorkShield MCP 서버 연결, 계약 유형 확인, 계약서 검토, 조항 단위 검색·분류, 결과 상태 해석 또는 streamable HTTP 연동이 필요한 경우에 사용한다.
---

# WorkShield MCP

WorkShield는 법률 결론을 내리지 않고 표준 대비 검토 후보와 참고 원문을 반환한다. 항상 결과를 검토 후보로 표시하고, 위법·합법·승소 가능성·계약상 유불리를 단정하지 않는다.

## 연결

기본 연결은 프로젝트의 Python 진입점을 `uv run`으로 실행하는 로컬 stdio 방식이다. MCP 클라이언트 설정에서 아래 프로세스를 자식 프로세스로 실행한다.

```text
command: uv
args: run --project <프로젝트-절대경로> python <프로젝트-절대경로>/src/app.py
env:
  PYTHONPATH: <프로젝트-절대경로>/src
  MCP_TRANSPORT: stdio
```

`file_path`는 이 방식처럼 서버와 파일시스템을 공유할 때만 사용한다. 서버 준비·MCP 설정·HTTP 연결이 필요하면 [references/setup.md](references/setup.md)를 읽는다.

## 기본 검토 흐름

1. `list_contract_types`로 현재 지원 계약 유형을 조회한다. 값을 하드코딩하지 않는다.
2. 계약 유형이 불명확하면 `assess_contract_scope`를 호출하고, 제안 유형을 사용자에게 보여 준다. 사용자가 최종 `contract_type`을 선택한다.
3. 전체 계약서의 검토 후보가 필요하면 `review_contract`를 호출한다. 한두 조항만 볼 때는 `parse_contract` 뒤 `classify_clause` 또는 `match_clause`를 사용한다.
4. 표준조항 본문 또는 참고 법령이 필요하면 리소스와 `get_grounding`을 조회한다.
5. 응답 상태와 각 결과의 `deviation`, `toxic_patterns`를 분리해 표시한다.

도구 선택, 입력 예시, 리소스 URI는 [references/tools-and-workflows.md](references/tools-and-workflows.md)를 읽는다.

## 결과 처리 원칙

- `NONE`은 표준조항 후보가 있다는 뜻일 뿐 안전·적법성 판단이 아니다.
- `EXTRA`와 `NO_MATCH`는 각각 추가 확인과 검색 후보 부재를 뜻한다.
- `MISSING`은 계약서 전체에 대응 조항이 보이지 않는 표준조항 후보이며, `user_clause`가 비어 있을 수 있다.
- `toxic_patterns`는 표준 대비 상태와 독립적인 주의 문구 유사 신호다. 빈 배열도 안전하다는 뜻이 아니다.
- `results=[]`이면 문제 없음으로 처리하지 말고 응답 `status`와 `message`를 먼저 확인한다.

상태별 사용자 안내와 파일 전송 규칙은 [references/response-and-safety.md](references/response-and-safety.md)를 읽는다.
