# WorkShield 🛡️

> 프리랜서 용역계약서를 표준계약서와 **조항 단위로 비교**해, 사람이 다시 확인할 지점을 찾는 RAG 기반 MCP 서비스

WorkShield는 사용자가 받은 계약서를 정부·공공기관 표준계약서와 대조해 **빠진 조항**, **추가된
조항**, **대응 후보를 찾지 못한 조항**을 구조화된 결과로 반환합니다. 법률 판단을 생성하는 대신,
재현 가능한 검색·매칭 결과를 바탕으로 검토 범위를 좁히는 것이 목표입니다.

| 한눈에 보기 | 내용 |
| --- | --- |
| 입력 | HWP/HWPX/PDF/DOCX 등 계약서 |
| 비교 단위 | 계약서의 `제N조` 조항 ↔ 계약 유형별 표준조항 |
| 1차 결과 | `NONE` · `EXTRA` · `MISSING` · `NO_MATCH` |
| 1차 실행 | LLM 없이 hybrid 검색 · rerank · 결정론 규칙 |
| 2차 실행 | MCP 서버 밖 데모/클라이언트에서 structured output LLM 사용 |
| 인터페이스 | FastMCP 도구·리소스, stdio/SSE/streamable HTTP |
| 품질 기준 | v5 골든 135건과 결정론적 평가 하니스 |

> WorkShield의 출력은 법률 자문이나 위법성 판단이 아니라 **표준 대비 검토 후보**입니다.

## 팀원

<table>
  <tr align="center">
    <td><img src="./assets/1.png" width="60"></td>
    <td><img src="./assets/2.png" width="60"></td>
    <td><img src="./assets/3.png" width="60"></td>
    <td><img src="./assets/4.png" width="60"></td>
    <td><img src="./assets/5.jpg" width="60"></td>
  </tr>
  <tr align="center">
    <td><b>박세빈</b></td>
    <td><b>홍철민</b></td>
    <td><b>김효선</b></td>
    <td><b>장규원</b></td>
    <td><b>박지유</b></td>
  </tr>
  <tr align="center" valign="top">
    <td>데이터 임베딩 처리,<br>독소 조항 수집 및 정의</td>
    <td>시스템 설계 및<br>mcp 구현</td>
    <td>eval 평가 및<br>테스트 계획 수립</td>
    <td>데이터 전처리 및<br>조항 카테고리 라벨링</td>
    <td>검색 파이프라인 구현</td>
  </tr>
</table>

---

## 무엇을 해결하나요?

계약서를 처음부터 끝까지 읽으면서 표준계약서와 수작업으로 비교하면 시간이 오래 걸리고, 긴 조항이나
비슷한 표현 사이에서 누락을 놓치기 쉽습니다. WorkShield는 이 과정을 다음과 같이 나눕니다.

1. 업로드한 계약서를 조항 단위로 분해합니다.
2. 각 사용자 조항과 가까운 표준조항을 hybrid 검색하고 rerank합니다.
3. 점수와 후보 유무에 따라 결정론적 검토 신호를 만듭니다.
4. 계약 전체에서 대응되지 않은 표준조항을 누락 후보로 추가합니다.
5. 알려진 독소 패턴 신호와 관련 법령 원문을 근거 자료로 연결합니다.
6. 필요한 경우에만 서버 밖 2차 LLM이 원문 간 의미 차이를 설명합니다.

```text
계약서 업로드
    ↓
kordoc 파싱 · 조항 분리
    ↓
Chroma dense + Kiwi/BM25 sparse 검색
    ↓
CrossEncoder rerank
    ↓
NONE / EXTRA / NO_MATCH 판정 ── 계약 전체 대조 ── MISSING 탐지
    ↓
독소 패턴 · 법령 근거 · 대응 표준조항
    ↓
MCP 구조화 응답 ── 선택적으로 서버 밖 2차 LLM 설명
```

## 판정 신호

| 신호 | 의미 |
| --- | --- |
| `NONE` | 표준조항과 1차 잠정 매칭된 조항. 의미가 완전히 같다는 법적 확정은 아님 |
| `EXTRA` | 근접 표준후보가 있더라도 매칭 임계값에 미치지 못한 추가·변형 검토 후보 |
| `NO_MATCH` | 검색 후보 자체가 없음을 나타내는 명시 상태 |
| `MISSING` | 사용자 계약 전체에서 대응 조항을 찾지 못한 표준조항 |

1차 MCP는 의미 동치성이나 유불리를 생성하지 않습니다. `NONE`과 `EXTRA`의 원문 비교·설명은
서버 밖 2차 계층의 책임이며, `MISSING`과 `NO_MATCH`는 2차 재판정 대상이 아닙니다.

## 핵심 특징

- **LLM 없는 1차 검토:** 동일한 입력과 인덱스에는 동일한 결과를 반환합니다.
- **조항 단위 근거:** 결과마다 사용자 조항, 대응 표준조항, confidence를 함께 제공합니다.
- **빈 응답 방지:** 검색 실패도 `NO_MATCH` 등 명시적인 상태로 반환합니다.
- **표준계약서 스코핑:** SW 프리랜서·SI 하도급·상용SW 유지관리 등 계약 유형별 코퍼스를 분리합니다.
- **양방향 검토 신호:** 표준 대비 누락뿐 아니라 별도 독소 패턴 검색 결과도 제공합니다.
- **법령 원문 연결:** `korean-law-mcp`를 통해 관련 법령 조문을 조회하되 해석을 덧붙이지 않습니다.
- **MCP 조합성:** 전체 계약 검토와 단일 조항 검색·분류를 각각 독립 도구로 사용할 수 있습니다.

## 아키텍처

코어 비즈니스 규칙과 외부 I/O를 분리한 헥사고날 구조입니다.

```text
contracts  ← 동결 enum · Pydantic 모델 · port
   ↑   ↑
core    adapter  ← 순수 판정 / DB·검색·문서·법령 I/O
   ↑   ↑
     pipe        ← 오프라인 코퍼스 빌드 + 런타임 검토 조립
       ↑
     server/     ← WorkShield 도구·리소스 + 법령 프록시 등록기
       ↑
     app.py      ← FastMCP 조립·lifespan·transport 실행
       ↑
  demo/client    ← 사용자 경험 + 서버 밖 2차 LLM
```

`src/server/` 자체가 실행 서버는 아닙니다. [`WorkShieldTools`](src/server/server.py)는 계약서
파싱·검색·검토 도구와 표준조항 리소스를, [`KoreanLawWrapper`](src/server/korean_law_wrapper.py)는 외부
`korean-law-mcp` 법령·판례 프록시 도구를 주입받은 FastMCP 인스턴스에 등록합니다. 최상위
[`src/app.py`](src/app.py)의 `create_app()`이 두 등록기를 하나의 앱으로 조립하고, 공용 법령 MCP 세션의
lifespan과 transport 실행을 관리합니다.

운영 환경에서는 MCP 서버와 Streamlit 데모를 별도 컨테이너로 실행하고, 임베딩·rerank 연산은 RunPod
Serverless GPU worker에 위임합니다. SQLite와 Chroma는 정규화 JSON과 migration SQL로부터 재생성되는
파생물입니다.

자세한 경계와 데이터 흐름은 [아키텍처 문서](docs/architecture.md)를 참고하세요.

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| 문서 변환 | kordoc |
| 임베딩 | `dragonkue/BGE-m3-ko` |
| reranker | `dragonkue/bge-reranker-v2-m3-ko` |
| 검색 | Chroma · Kiwi · BM25 · RRF |
| 저장소 | SQLite · Chroma |
| 법령 근거 | korean-law-mcp |
| 서버 | Python · FastMCP · Pydantic |
| 데모 | Streamlit · structured output LLM |
| 개발·검증 | uv · just · pytest · Docker |

## 빠른 시작

### 준비물

- Python 3.13 이상
- [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)
- Node.js — kordoc와 korean-law-mcp CLI 실행에 사용

### 설치와 실행

```bash
cp .env.example .env
just setup
just build-db
just test unit
just run-mcp
```

기본 `just run-mcp`는 stdio transport로 서버를 실행합니다. HTTP로 실행하려면 다음 명령을 사용합니다.

```bash
just run-mcp streamable-http 8000
```

MCP Inspector에서 도구를 직접 호출하려면:

```bash
just run-mcp-ui
```

### 데모와 Docker

```bash
just docker-build
just demo-bundle-up
```

데모는 `http://localhost:8501`, MCP streamable HTTP endpoint는 `http://localhost:8000/mcp`에서
접근할 수 있습니다.

```bash
just demo-bundle-down
```

## 환경 변수

`.env.example`을 복사한 뒤 필요한 값만 로컬 `.env`에 설정합니다. `.env`는 Git에 커밋하지 않습니다.

| 변수 | 용도 |
| --- | --- |
| `APP_ENV` | `local` 또는 `prod` 실행 환경 |
| `OPEN_LAW_API_KEY` | 법령 API 인증 |
| `KOREAN_LAW_MCP_URL` | 외부 korean-law-mcp endpoint |
| `RUNPOD_API_KEY` | 운영 GPU worker 인증 |
| `RUNPOD_ENDPOINT_ID` | RunPod Serverless endpoint |

로컬 단위 테스트에는 모든 외부 키가 필요하지 않습니다. 운영 실행과 법령·RunPod 연동에는 해당 키를
설정해야 합니다.

## MCP 도구와 리소스

최종 MCP 표면은 `src/app.py`가 `WorkShieldTools`와 `KoreanLawWrapper`를 조립해 만듭니다.
`server.py`가 단독으로 모든 도구를 노출하거나 실행되는 구조가 아닙니다.

### WorkShield 1차 도구

| 도구 | 역할 |
| --- | --- |
| `assess_contract_scope` | 지원 범위와 계약 유형 후보를 사전 점검 |
| `parse_contract` | 계약서 파일을 조항 목록으로 분해 |
| `match_clause` | 단일 조항과 가까운 표준조항 후보 검색 |
| `classify_clause` | 단일 조항 검색·rerank·1차 판정 |
| `review_contract` | 계약서 전체 파싱·매칭·누락·독소·근거 조회 |
| `get_grounding` | 카테고리 또는 조항에 관련된 법령 원문 조회 |
| `list_contract_types` | 지원 계약 유형 조회 |
| `list_categories` | 표준조항 카테고리와 검색 앵커 조회 |
| `list_toxic_patterns` | 독소 패턴 종류 조회 |
| `list_toxic_pattern_details` | 독소 패턴의 상세 기준 조회 |

`WorkShieldTools`는 읽기 전용 MCP resource도 함께 등록합니다.

- `standard://{contract_type}` — 계약 유형별 표준조항 목록
- `standard://{contract_type}/{clause_id}` — 특정 표준조항 원문

### 외부 법령 MCP 프록시 도구

`KoreanLawWrapper`는 2차 클라이언트가 법령·판례 원문과 검증 기능을 사용할 수 있도록 다음 도구를 같은
WorkShield MCP 표면에 등록합니다. WorkShield 서버가 LLM 해석을 생성하는 것이 아니라, 공용
`KoreanLawMCPClient`를 통해 외부 `korean-law-mcp` 기능을 전달하는 계층입니다.

| 도구 | 역할 |
| --- | --- |
| `search_law` | 법령명 키워드로 법령 식별자 검색 |
| `get_law_text` | 법령·조문 본문 조회 |
| `get_annexes` | 법령의 별표·서식 조회 |
| `legal_research` | 외부 법률 MCP의 다단계 리서치 실행 |
| `legal_analysis` | 외부 법률 MCP의 인용 검증·행위시법 분석 실행 |
| `discover_tools` | 외부 법률 MCP의 추가 도구 탐색 |
| `execute_tool` | 탐색한 외부 도구 실행 |
| `search_decisions` | 판례·해석례 등 결정 검색 |
| `get_decision_text` | 결정 식별자로 전문 조회 |

## 자주 쓰는 명령

| 명령 | 용도 |
| --- | --- |
| `just build-db` | 정규화 데이터로 SQLite와 Chroma 재생성 |
| `just test unit` | 외부 연동을 제외한 결정론적 단위 테스트 |
| `just test integration` | 외부 DB·모델이 필요한 통합 테스트 |
| `just eval a v5` | 활성 v5 Track A 평가 |
| `just run-mcp` | 로컬 MCP 서버 실행 |
| `just run-mcp-ui` | MCP Inspector 실행 |
| `just docker-build` | 운영 MCP 이미지 빌드 |
| `just demo-bundle-up` | MCP와 데모 컨테이너 실행 |
| `just embed-on` / `just embed-off` | RunPod worker 활성화·과금 차단 |

전체 레시피는 `just --list`로 확인할 수 있습니다.

## 품질 기준과 현재 상태

1차의 활성 회귀 기준은 **v5 골든 135건**입니다. SI·SM·SW 유형별 45건으로 구성되며, 지표는
LLM-judge 없이 결정론적으로 계산합니다.

- 기본 임계값: `match_threshold=0.50`, `toxic_threshold=0.60`
- 독소 제목 접두 실험 S: tuning 실패로 폐기
- SW OVER_MATCH 규칙 C1: held-out FP 기준 초과로 보류
- 1차 검색·임계값·독소 패턴의 추가 튜닝: 종료
- 현재 활성 작업: 서버 밖 **K — 2차 structured output LLM 제품화**

현재 상태는 [START_HERE](docs/START_HERE.md), 동결 수치와 실험 근거는
[품질 기준](docs/quality/baseline-v5.md), 다음 작업은 [로드맵](docs/roadmap.md)에서 확인할 수 있습니다.

## 프로젝트 구조

```text
src/
  app.py       FastMCP 앱 조립·외부 세션 lifespan·실행 진입점
  contracts/   동결 enum·모델·port
  core/        외부 I/O 없는 순수 검색·판정 규칙
  adapter/     DB·벡터·모델·문서·법령 연동
  pipe/        데이터 준비와 런타임 검토 파이프라인
  server/      WorkShield 도구·리소스와 법령 프록시 등록 클래스
quality/       활성 평가 코드와 v5 회귀 fixture
demo/          Streamlit UI와 서버 밖 2차 LLM
data/          표준계약서 원천·정규화 데이터·migration
tests/         단위·통합 테스트
docs/          현재 상태·아키텍처·결정·품질 근거
```

완료·폐기된 작업과 과거 평가 기록은 [docs/archive](docs/archive/)에 보존합니다. 개발자가 가장 먼저 볼
문서는 [docs/START_HERE.md](docs/START_HERE.md)입니다.

## 프로젝트 원칙

- 1차 MCP 서버에는 LLM 호출을 넣지 않습니다.
- 동결된 계약 모델과 MCP 시그니처는 승인 없이 변경하지 않습니다.
- 사용자 표면에서는 항상 “검토 후보”로 표현합니다.
- 매칭 실패와 빈 결과를 조용히 숨기지 않습니다.
- 평가는 LLM-judge 없이 재현 가능한 계산으로 수행합니다.

## 주요 문서

- [현재 상태와 실행 안내](docs/START_HERE.md)
- [시스템 아키텍처](docs/architecture.md)
- [현재 로드맵](docs/roadmap.md)
- [v5 품질 기준선](docs/quality/baseline-v5.md)
- [날짜별 의사결정](docs/decisions/)
- [필수 산출물](docs/deliverables/)
- [보안 정책](docs/보안정책.md)

## 라이선스와 출처

표준계약서와 법령 자료의 권리는 각 배포 기관에 있습니다. 모델·라이브러리·샘플 자료를 사용할 때는
각 원출처의 라이선스와 이용 조건을 따릅니다.
