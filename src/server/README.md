# server — MCP 클라이언트 통합 가이드

이 디렉터리는 WorkShield의 계약서 검토 도구와 표준조항 리소스를 MCP 앱에 등록합니다. MCP
클라이언트는 계약서와 비교할 계약 유형을 전달해, **표준 대비 검토가 필요한 조항과 참고 자료**를
구조화된 결과로 받을 수 있습니다.

> 결과는 법률 자문, 위법성 또는 계약상 유불리 판단이 아닙니다. 클라이언트에는 항상 “검토 후보”로
> 표시하세요.

## 시작하기

서버는 이 디렉터리가 아니라 최상위 [`src/app.py`](../app.py)에서 실행합니다.

```bash
just run-mcp                         # stdio
just run-mcp streamable-http 8000   # streamable HTTP
just run-mcp-ui                      # MCP Inspector
```

네트워크 환경의 streamable HTTP endpoint는 `http://localhost:8000/mcp`입니다. 실행 환경과
외부 연동 설정은 루트 [README](../../README.md)를 참고하세요.

## 계약서 전체 검토

`review_contract`는 계약서를 조항별로 비교하고, 계약서 전체에서 찾지 못한 표준조항도 함께
반환합니다. 계약 유형이 확실하면 바로 호출하고, 확실하지 않으면 먼저 `assess_contract_scope`를
호출하세요.

### 1. 비교할 계약 유형 선택

`contract_type`은 파일에서 자동으로 확정되는 값이 아닙니다. 이 값이 어떤 표준조항 모음과 비교할지를
정하므로, 클라이언트가 최종 값을 선택해야 합니다. 지원 값은 하드코딩하지 말고
`list_contract_types`로 조회하세요.

유형이 불명확한 경우의 권장 흐름은 다음과 같습니다.

1. `assess_contract_scope`에 파일을 전달합니다.
2. 응답의 `status`, `suggested_contract_type`, `candidates`를 사용자에게 보여 줍니다.
3. 사용자가 확인하거나 선택한 `contract_type`으로 `review_contract`를 호출합니다.

| `assess_contract_scope.status` | 클라이언트 처리 |
| --- | --- |
| `IN_SCOPE` | 제안 유형을 기본값으로 보여 주고 사용자가 확인·변경하게 합니다. |
| `CONTRACT_TYPE_UNCERTAIN` | 유형 근거가 부족함을 알립니다. 자동으로 확정하지 말고 사용자가 선택한 유형으로 계속할 수 있게 합니다. |
| `OUT_OF_SCOPE` | 현재 표준 코퍼스와의 공통 근거가 부족하다고 알립니다. 계속 진행한다면 사용자의 명시적 재확인을 받습니다. |
| `EMPTY_DOCUMENT` | 조항을 찾지 못한 상태입니다. 전체 검토를 호출하지 말고 파일 형식·스캔 상태를 확인하게 합니다. |

`assess_contract_scope`와 `review_contract`는 각각 파일을 파싱합니다. 유형이 이미 확실한
워크플로우에서는 `review_contract`를 직접 호출해 파일 전송과 파싱을 한 번 줄일 수 있습니다.

### 2. 파일 전달

- 로컬 stdio 환경에서는 `file_path`를 전달합니다.
- 네트워크 환경에서는 base64 `file_content`와 `file_name`을 함께 전달합니다.
- 두 방식은 동시에 사용할 수 없습니다.
- 지원 형식은 `HWP`(3.x/5.x), `HWPX`, `HWPML`, `PDF`, `XLS`, `XLSX`, `DOCX`입니다. 확장자는
  대소문자를 구분하지 않으며, 지원하지 않는 형식과 확장자 없는 파일은 파싱 전에 거절됩니다.

### 3. 결과 표시와 상태 해석

`review_contract.results`의 각 항목은 표준 대비 검토 후보입니다. 아래 상태를 법적 결론처럼
표시하거나 자동으로 계약서 내용을 변경해서는 안 됩니다.

| 상태 | 클라이언트에 표시할 의미 | 비교 방향 |
| --- | --- | --- |
| `NONE` | 대응하는 표준조항 후보를 찾음 | 사용자 조항 → 표준조항 |
| `EXTRA` | 비슷한 표준조항은 있으나 충분한 대응으로 보기 어려워 추가 확인이 필요함 | 사용자 조항 → 표준조항 |
| `NO_MATCH` | 이 사용자 조항의 표준조항 검색 후보를 찾지 못함 | 사용자 조항 → 표준조항 |
| `MISSING` | 표준조항은 있으나 계약서 전체에서 대응 조항을 찾지 못해 누락 가능성이 있음 | 표준조항 → 계약서 전체 |

`NO_MATCH`와 `MISSING`은 방향이 다릅니다. 전자는 **계약서에 있는 특정 조항**의 비교 후보가 없는
상태이고, 후자는 **표준계약서에 있는 조항**이 계약서 전체에서 보이지 않는 상태입니다. `MISSING`
결과는 `user_clause`가 빈 문자열일 수 있습니다.

`toxic_patterns`는 표준 대비 상태와 별개로, 알려진 주의 문구와 유사한 표현을 찾은 보조 신호입니다.
빈 목록은 해당 문구가 안전하거나 문제가 없다는 뜻이 아닙니다. `grounding`은 관련 법령 원문
참고자료이며 적용 여부나 법률 해석을 확정하지 않습니다.

`results=[]`를 “문제 없음”으로 처리하지 마세요. `EMPTY_DOCUMENT`, `CORPUS_UNAVAILABLE`,
`INVALID_CONFIG`, `PIPELINE_ERROR` 중 응답 `status`를 먼저 확인해 사용자에게 적절한 다음 행동을
안내해야 합니다.

## 도구와 리소스

### 계약서 검토 도구

| 도구 | 용도 |
| --- | --- |
| `assess_contract_scope` | 지원 범위와 계약 유형 후보 사전 점검 |
| `review_contract` | 계약서 전체 파싱·비교·누락 후보·주의 문구·참고자료 조회 |
| `parse_contract` | 계약서 파일을 조항 목록으로 분해 |
| `match_clause` | 단일 조항과 가까운 표준조항 후보 검색 |
| `classify_clause` | 단일 조항의 검색·재정렬·표준 대비 상태 판정 |
| `get_grounding` | 카테고리 또는 조항에 관련된 법령 원문 조회 |

`MISSING`은 계약서 전체를 비교해야 찾을 수 있으므로 `classify_clause`에서는 반환되지 않습니다.
`classify_clause`는 주의 문구 검색과 법령 조회를 수행하지 않습니다. 해당 정보가 필요하면
`review_contract`를 사용하세요.

### 조회 도구와 표준조항 리소스

| 도구 | 용도 |
| --- | --- |
| `list_contract_types` | 지원 계약 유형 조회 |
| `list_categories` | 표준조항 카테고리와 검색 앵커 조회 |
| `list_toxic_patterns` | 주의 문구 패턴 종류 조회 |
| `list_toxic_pattern_details` | 주의 문구 패턴의 상세 기준 조회 |

- `standard://{contract_type}` — 계약 유형별 표준조항 목록
- `standard://{contract_type}/{clause_id}` — 특정 표준조항 원문

### 법령·판례 프록시 도구

동일 MCP 앱에는 외부 `korean-law-mcp`를 통해 법령과 판례 원문을 조회하는 도구도 등록됩니다.
이 도구들은 원문·검색 기능을 전달할 뿐 WorkShield가 법률 해석을 생성하지는 않습니다.

| 도구 | 용도 |
| --- | --- |
| `search_law` / `get_law_text` / `get_annexes` | 법령·조문·별표 및 서식 조회 |
| `search_decisions` / `get_decision_text` | 판례·해석례 등 결정 검색과 전문 조회 |
| `legal_research` / `legal_analysis` | 외부 법률 MCP의 리서치·인용 검증 기능 호출 |
| `discover_tools` / `execute_tool` | 외부 법률 MCP의 추가 도구 탐색과 실행 |

## 구현 구조

`src/server/`는 MCP 입출력 변환과 도구·리소스 등록만 담당합니다. 검색과 판정 규칙은 `core`,
런타임 검토 흐름은 `pipe`, DB·문서·모델·법령 I/O는 `adapter`에 있습니다.

```text
외부 MCP 클라이언트
        ↓
src/app.py                   FastMCP 앱 생성·실행·공용 세션 관리
        ↓
src/server/
  ├─ WorkShieldTools         계약서 검토 도구·표준조항 리소스 등록
  └─ KoreanLawWrapper        외부 법령 MCP 프록시 도구 등록
        ↓
core / pipe / adapter        판정 규칙 / 검토 조립 / 외부 I/O
```

[`src/app.py`](../app.py)의 `create_app()`이 `FastMCP("WorkShield")` 인스턴스를 만들고,
`WorkShieldTools`와 `KoreanLawWrapper`를 등록합니다. 또한 앱 lifespan에서 공용
`KoreanLawMCPClient` 세션을 열고 종료 시 닫습니다. `get_grounding`과 법령 프록시 도구는 이
클라이언트의 세션과 TTL 캐시를 공유합니다.

모듈 수준의 함수는 직접 단위 테스트와 하위호환을 위해 유지하지만, MCP에는
`WorkShieldTools` 인스턴스 메서드만 등록됩니다.

제품 경계와 현재 상태는 [START_HERE](../../docs/START_HERE.md), 전체 아키텍처는
[architecture.md](../../docs/architecture.md)를 참고하세요.
