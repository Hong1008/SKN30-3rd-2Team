# MCP 정적 문서 UI 및 GitHub Pages 배포 계획

## 목적

현재 FastMCP에 등록된 도구, 리소스, 리소스 템플릿, 프롬프트의 런타임 discovery 결과를 사람이
탐색하기 쉬운 정적 웹 문서로 제공한다. 문서의 단일 데이터 원천은 `just build-mcp-docs`가 생성하는
`site/mcp-spec.json`이며, 문서 UI는 이 파일을 읽어 렌더링한다.

이 문서는 MCP를 REST API로 변환하거나 OpenAPI 계약을 별도로 관리하지 않는다. OpenAPI/Swagger UI는
HTTP REST API 문서 형식이므로, MCP의 `tools/list`, `resources/list`,
`resources/templates/list`, `prompts/list` discovery 표면을 정확히 표현하는 전용 UI를 사용한다.

## 구현 상태

- [x] `site/mcp_spec.py`와 `just build-mcp-docs`로 현재 FastMCP 명세를 생성한다.
- [x] `site/index.html`, `site/styles.css`, `site/app.js`로 검색·분류·입출력 스키마 탐색 UI를 제공한다.
- [x] `site/.nojekyll`을 포함하고, 정적 자산·최신 명세를 회귀 테스트로 검증한다.
- [x] `.github/workflows/deploy-mcp-docs.yml`로 `main` push와 수동 실행 시 Pages artifact를 배포한다.
- [ ] 저장소 Settings → Pages에서 publishing source를 **GitHub Actions**로 선택한다.

## 현재 기반

- `just build-mcp-docs`는 `site/mcp_spec.py`를 실행해 `create_app()`의 현재 등록 상태를
  `site/mcp-spec.json`에 생성한다.
- 명세에는 서버 이름, 도구의 설명·입력 스키마·출력 스키마, 고정 리소스, 리소스 템플릿, 프롬프트를
  포함한다.
- 배열은 이름 또는 URI 순으로 정렬해 불필요한 diff를 방지한다.
- `tests/server/test_mcp_spec.py`는 저장된 명세가 현재 FastMCP 등록 결과와 일치하는지 검증한다.
- `standard://{contract_type}` 및 `standard://{contract_type}/{clause_id}` 리소스 템플릿은 설명과
  `application/json` MIME 타입을 노출한다.

## 산출물과 경로

| 경로 | 역할 | Git 관리 |
| --- | --- | --- |
| `site/mcp_spec.py` | FastMCP discovery를 문서 명세로 생성하는 스크립트 | 관리 |
| `site/mcp-spec.json` | FastMCP discovery의 검토 가능한 JSON 스냅샷 | 관리 |
| `site/index.html`, `site/*.css`, `site/*.js` | 정적 문서 UI 소스와 빌드 산출물 | 관리 |
| `.github/workflows/deploy-mcp-docs.yml` | Pages 빌드·배포 워크플로 | 관리 |

웹 문서와 관련된 모든 파일은 `site/`에서 관리하고 Git에 포함한다. GitHub Actions는 이 디렉터리 전체를
GitHub Pages artifact로 업로드한다.

## 문서 UI 범위

### 정보 구조

- 첫 화면에는 서버 이름, 명세 포맷 버전, 도구·리소스·리소스 템플릿·프롬프트 개수를 표시한다.
- 왼쪽 탐색 영역에는 전체 검색과 `Tools`, `Resources`, `Resource templates`, `Prompts` 분류를 둔다.
- 도구 상세에는 설명, 입력 JSON Schema, 출력 JSON Schema, required 필드, enum, 기본값을 표시한다.
- 리소스 템플릿 상세에는 URI 템플릿, MIME 타입, 설명, 사용할 식별자와 선행 조회 방법을 표시한다.
- JSON Schema의 `$defs`와 `$ref`는 링크 또는 펼침 UI로 연결해 중첩 DTO를 읽을 수 있게 한다.
- 실행 버튼은 포함하지 않는다. 이 사이트는 문서 사이트이며 실제 호출·디버깅은 MCP Inspector가 담당한다.

### 표시 원칙

- 도구 함수 docstring과 Pydantic `Field(description=...)`가 생성한 설명을 원문 의미가 바뀌지 않게
  표시한다.
- 검토 후보, 빈 결과, 점수, 법률 판단 비단정 등의 경계 문구는 생략하거나 축약하지 않는다.
- 비밀값, 배포 환경변수 값, 사용자 계약서, 운영 DB 데이터는 문서에 포함하지 않는다.
- 모바일 화면에서도 스키마와 긴 설명을 읽을 수 있도록 반응형 레이아웃을 적용한다.

## 빌드 명령

`just build-mcp-docs`를 추가한다. 이 명령은 다음 순서로 실행한다.

1. `site/mcp_spec.py`를 실행해 최신 `site/mcp-spec.json`을 생성한다.
2. `site/`의 HTML, CSS, JavaScript가 `mcp-spec.json`을 읽어 문서 UI를 구성한다.
3. GitHub Pages가 Jekyll 변환을 수행하지 않도록 필요한 경우 `site/.nojekyll`을 생성한다.
4. 생성 결과에 `index.html`과 `mcp-spec.json`이 있는지 확인한다.

UI는 외부 CDN에 의존하지 않는 순수 정적 HTML/CSS/JavaScript로 시작한다. 이 방식은 별도 Node 빌드 체인,
런타임 서버, API 키 없이 로컬과 GitHub Actions에서 동일하게 재현된다.

## GitHub Pages 배포

`.github/workflows/deploy-mcp-docs.yml` 워크플로를 추가한다.

- 트리거: 기본 브랜치에 대한 push 및 수동 `workflow_dispatch`.
- build job: checkout → Python 3.13 설정 → `uv sync --frozen` → `just build-mcp-docs` →
  `actions/configure-pages` → `actions/upload-pages-artifact`.
- deploy job: build job 완료 후 `actions/deploy-pages`로 artifact를 `github-pages` environment에 배포.
- 권한: build에는 `contents: read`, deploy에는 `pages: write`, `id-token: write`를 명시한다.
- pull request에서는 선택적으로 build·UI 검증까지만 수행하고 Pages 배포는 하지 않는다.

저장소 설정에서 Pages의 publishing source를 **GitHub Actions**로 한 번 선택해야 한다. 공개 저장소의
Pages는 공개되므로, 명세에 공개하면 안 되는 정보가 추가되지 않도록 회귀 검증과 코드 리뷰에서 확인한다.

## 검증 계획

1. exporter 단위 테스트: 현재 FastMCP 등록 결과와 JSON 명세의 동치성, 리소스 설명과 MIME 타입을 검증한다.
2. UI 빌드 테스트: `site/`에 `index.html`, `mcp-spec.json` 및 필수 정적 자산이 있는지 검증한다.
3. UI 데이터 테스트: 도구 1개와 리소스 템플릿 2개의 설명·입출력 스키마가 생성 HTML 또는 렌더링 데이터에
   포함되는지 검증한다.
4. CI 검증: 기본 브랜치 push에서 Pages artifact 생성과 배포 결과 URL을 확인한다.
5. 변경 절차: 도구/리소스/DTO 스키마를 변경하면 `just build-mcp-docs`를 실행하고,
   명세 스냅샷 및 UI 회귀 테스트를 함께 갱신한다.

## 구현 순서

1. `site/`에 검색·분류·스키마 표시 기능을 갖춘 정적 UI를 작성한다.
2. `just build-mcp-docs`가 `site/mcp-spec.json`을 최신 등록 상태로 생성하도록 유지한다.
3. UI 빌드·데이터 회귀 테스트를 추가한다.
4. GitHub Pages Actions workflow를 추가한다.
5. 저장소 Settings → Pages에서 source를 GitHub Actions로 설정하고, 배포 URL을 README 또는 시작 문서에 연결한다.
