# server — MCP 도구·리소스 등록 계층

이 디렉터리는 WorkShield의 MCP 기능을 구현하고, **주입받은 `FastMCP` 인스턴스에 등록하는 클래스**를
제공합니다. 자체적으로 서버를 생성하거나 실행하지 않습니다. 최종 조립과 실행 진입점은
[`src/app.py`](../app.py)입니다.

```text
src/server/server.py
  └─ WorkShieldTools ─────────────┐
                                  │
src/server/korean_law_wrapper.py  │
  └─ KoreanLawWrapper ────────────┼─→ src/app.py:create_app()
                                  │       ├─ FastMCP("WorkShield") 생성
adapter.korean_law_mcp.koreanLaw ─┘       ├─ 두 등록기 조립
                                          ├─ 공용 법령 세션 lifespan
                                          └─ transport 실행
```

## 조립과 실행

[`src/app.py`](../app.py)의 `create_app()`은 다음 순서로 MCP 앱을 만듭니다.

1. lifespan이 설정된 `FastMCP("WorkShield")` 인스턴스를 생성합니다.
2. `WorkShieldTools(mcp)`로 1차 계약 검토 도구와 표준조항 리소스를 등록합니다.
3. `KoreanLawWrapper(mcp, client=koreanLaw)`로 외부 법령 MCP 프록시 도구를 등록합니다.
4. 앱 lifespan에서 공용 `koreanLaw` 클라이언트 세션을 열고 종료 시 닫습니다.
5. `main()`이 `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT` 설정에 맞춰 앱을 실행합니다.

1차 `get_grounding`과 2차 법령 프록시는 같은 `KoreanLawMCPClient`의 자식 프로세스·세션·TTL 캐시를
재사용합니다. 실행은 `server.py`가 아니라 항상 최상위 앱을 기준으로 합니다.

```bash
just run-mcp                         # stdio
just run-mcp streamable-http 8000   # streamable HTTP
just run-mcp-ui                      # MCP Inspector
```

## `server.py` — WorkShieldTools

[`server.py`](server.py)는 계약 검토 함수와 `WorkShieldTools` 등록 클래스를 정의합니다. 모듈 함수는
직접 단위 테스트와 하위호환을 위해 유지하지만, MCP에는 `WorkShieldTools`의 인스턴스 메서드만
`mcp.add_tool()`로 등록됩니다.

| 도구 | 역할 |
| --- | --- |
| `parse_contract` | 계약서 파일을 조항 목록으로 분해 |
| `assess_contract_scope` | 지원 범위와 계약 유형 후보를 사전 점검 |
| `match_clause` | 단일 조항과 가까운 표준조항 후보 검색 |
| `classify_clause` | 단일 조항 검색·rerank·1차 판정 |
| `review_contract` | 계약서 전체 파싱·매칭·누락·독소·근거 조회 |
| `get_grounding` | 카테고리 또는 조항에 관련된 법령 원문 조회 |
| `list_contract_types` | 지원 계약 유형 조회 |
| `list_categories` | 표준조항 카테고리와 검색 앵커 조회 |
| `list_toxic_patterns` | 독소 패턴 종류 조회 |
| `list_toxic_pattern_details` | 독소 패턴 상세 기준 조회 |

`WorkShieldTools`는 다음 읽기 전용 resource도 등록합니다.

- `standard://{contract_type}` — 계약 유형별 표준조항 목록
- `standard://{contract_type}/{clause_id}` — 특정 표준조항 원문

## MCP 클라이언트 통합 가이드

### 계약서 전체 검토 흐름

`contract_type`은 파일에서 자동 추정되는 값이 아니라, `review_contract`가 비교에 사용할 표준
코퍼스를 지정하는 입력입니다. `review_contract`는 지원 enum인지 확인한 뒤 그 유형으로만 표준조항
검색·누락 탐지를 수행하며, 첨부 문서 본문과의 유형 일치를 검증하거나 값을 자동 변경하지 않습니다.

유형이 불명확하거나 사용자가 선택한 유형과 문서 내용이 다를 가능성이 있으면 아래 흐름을 사용하세요.

1. `assess_contract_scope`에 `file_path` 또는 `file_content`와 `file_name`을 전달합니다.
2. 응답의 `status`, `suggested_contract_type`, `candidates`를 사용자에게 보여 주고 최종
   `contract_type`을 선택받습니다.
3. 선택된 `contract_type`으로 같은 파일을 `review_contract`에 전달합니다.

| `assess_contract_scope.status` | 클라이언트 처리 |
| --- | --- |
| `IN_SCOPE` | `suggested_contract_type`을 기본값으로 제시하고, 사용자가 확인하거나 변경한 유형으로 검토합니다. |
| `CONTRACT_TYPE_UNCERTAIN` | 유형 근거가 부족하다는 경고를 표시합니다. 자동 선택·차단하지 말고, 사용자가 명시한 유형으로 검토를 계속할 수 있습니다. |
| `OUT_OF_SCOPE` | 현재 지원 표준 코퍼스와의 공통 근거가 부족하다고 안내하고, 기본적으로 검토 대상에서 제외합니다. 계속 진행하는 정책이라면 사용자의 명시적 재확인을 받습니다. |
| `EMPTY_DOCUMENT` | 조항을 찾지 못한 상태입니다. `review_contract`를 호출하지 말고 파일 형식·스캔 상태를 확인하도록 안내합니다. |

`assess_contract_scope`와 `review_contract`는 각각 파일을 파싱합니다. 사전 점검 뒤 전체 검토를
호출하면 파일 전송·파싱이 두 번 발생하므로, 이미 계약 유형이 확실한 워크플로우에서는
`review_contract`를 직접 호출할 수 있습니다. 반대로 유형 불일치 방지가 필요한 워크플로우에서는
사전 점검을 기본 단계로 둡니다.

### 입력과 결과 해석

- 로컬 stdio 환경에서는 `file_path`를, 네트워크 환경에서는 base64 `file_content`와 `file_name`을
  함께 전달합니다. 두 입력 방식은 동시에 사용할 수 없습니다.
- 원본 파일은 `HWP`(3.x/5.x), `HWPX`, `HWPML`, `PDF`, `XLS`, `XLSX`, `DOCX`만 지원합니다.
  확장자는 대소문자를 구분하지 않으며, 다른 형식 또는 확장자 없는 파일은 파싱 전에 명시적으로 거절됩니다.
- 지원 유형은 하드코딩하지 말고 `list_contract_types`로 조회합니다.
- `review_contract`의 `results`는 표준 대비 검토 후보입니다. `NONE`, `EXTRA`, `MISSING`,
  `NO_MATCH` 및 `toxic_patterns`는 위법·합법이나 유불리를 단정하지 않습니다.
- `results=[]`는 문제 없음이 아닙니다. `EMPTY_DOCUMENT`, `CORPUS_UNAVAILABLE`,
  `INVALID_CONFIG`, `PIPELINE_ERROR` 중 어떤 `status`인지 먼저 확인합니다.

## `korean_law_wrapper.py` — KoreanLawWrapper

[`korean_law_wrapper.py`](korean_law_wrapper.py)의 `KoreanLawWrapper`는 2차 LLM 클라이언트가 법령·판례
원문과 검증 기능을 조합할 수 있도록 외부 `korean-law-mcp` 기능 9개를 동일한 FastMCP 앱에 명시적으로
등록합니다.

| 프록시 도구 | 역할 |
| --- | --- |
| `search_law` | 법령명 키워드로 법령 식별자 검색 |
| `get_law_text` | 법령 식별자와 선택 조문 코드로 본문 조회 |
| `get_annexes` | 법령의 별표·서식 조회 |
| `legal_research` | 외부 법률 MCP의 다단계 리서치 실행 |
| `legal_analysis` | 외부 법률 MCP의 인용 검증·행위시법 분석 실행 |
| `discover_tools` | 외부 법률 MCP의 추가 도구 탐색 |
| `execute_tool` | 탐색한 외부 도구를 지정 인자로 실행 |
| `search_decisions` | 판례·해석례 등 결정 검색 |
| `get_decision_text` | 결정 식별자로 전문 조회 |

이 클래스는 법률 해석을 자체 생성하거나 LLM을 호출하지 않습니다. 주입받은
`KoreanLawMCPClient`에 요청을 전달하는 MCP 어댑터이며, 사용자 표면의 해석과 structured output은
서버 밖 2차 클라이언트의 책임입니다.

## 계층 경계

- `src/server/`는 MCP 입출력 변환과 도구·리소스 등록을 담당합니다.
- `src/app.py`는 FastMCP 인스턴스, 등록기, 외부 세션, transport를 조립합니다.
- 검색·판정 규칙은 `core`, 런타임 흐름은 `pipe`, 외부 통신은 `adapter`에 둡니다.
- 1차 WorkShield 도구에는 LLM 호출이나 생성형 법률 해석을 넣지 않습니다.
- 실패와 미매칭은 빈 응답으로 숨기지 않고 구조화된 status 또는 `NO_MATCH`로 반환합니다.

현재 제품 경계는 [START_HERE](../../docs/START_HERE.md), 전체 구조는
[architecture.md](../../docs/architecture.md)를 참고하세요.
