# demo

> **Deprecated**: 이 Streamlit 데모는 현행 WorkShield MCP의 제품 표면이나 지원 대상이 아니다.
> 1차 MCP의 품질·계약·완료 상태와 무관한 과거 시연용 예시다. 새 클라이언트는 이 구현이나 LLM
> provider·프롬프트·출력 형식을 따를 필요가 없으며, MCP 통합 가이드를 기준으로 독립 구현한다.
> Docker 이미지·Compose 번들·루트 workspace에서는 제거됐으므로 배포 대상이 아니다.

WorkShield Streamlit 데모. MCP 서버(루트)와는 별개 프로세스/컨테이너로 실행한다.

## 과거 로컬 실행 방법

- 터미널1: `just run-mcp streamable-http 8000`
- 터미널2: `uv run --project demo streamlit run demo/streamlit_app.py`
