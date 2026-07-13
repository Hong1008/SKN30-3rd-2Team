# pipe

표준 코퍼스 빌드와 `review_contract` 런타임 조립을 담당합니다. core 순수 함수와 adapter 구현을
주입해 연결하며, 1차에는 LLM을 호출하지 않습니다. 실행 흐름은 [architecture](../../docs/architecture.md)를
참조하세요.
