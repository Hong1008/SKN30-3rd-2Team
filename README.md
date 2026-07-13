# WorkShield 🛡️

> IT·SW 분야의 도급·하도급 계약서를 표준계약서와 조항별로 비교하고, 관련 표준조항과 법령 원문을 RAG 컨텍스트로 제공하는 MCP 서버

프리랜서·긱워커는 계약 형태가 제각각이라, 저작권·2차 가공 권리, 과업 범위, 대금 지급 같은
핵심 조건을 스스로 검토하기 어렵습니다. 변호사 자문에는 비용 장벽이 있고, 기존 서비스는 정책을
나열하거나 단순 위반 여부만 안내하는 경우가 많습니다.

WorkShield는 계약서에서 **표준과 대응하는 조항**, **별도 확인이 필요한 조항**,
**누락 가능성이 있는 표준조항**과 **주의 문구 유사 신호**를 찾아 구조화된 결과로
반환합니다. 사람이 계약서와 표준계약서를 처음부터 모두 대조하는 대신, 먼저 보아야 할 부분을
좁혀주는 것이 목적입니다.

이 저장소는 웹 화면이 아닌 **MCP 서버**를 제공합니다. MCP 클라이언트는 검색된 표준조항과 법령
원문을 근거로 사용해 필요한 사용자 경험과 자연어 설명을 구성할 수 있습니다.

| 한눈에 보기 | 내용 |
| --- | --- |
| 현재 주요 대상 | SW 프리랜서 도급·용역, SI·SM 하도급 |
| 입력 | HWP 3.x/5.x, HWPX, HWPML, PDF, XLS, XLSX, DOCX 계약서 |
| 비교 단위 | 사용자 계약서의 `제N조` 조항 ↔ 계약 유형별 표준조항 |
| 제공 결과 | 조항별 대응 상태, 누락 가능성, 주의 문구 유사 신호, 관련 법령 원문 |
| 제공 형태 | FastMCP 도구·리소스, stdio/SSE/streamable HTTP |
| 특성 | 검색·재정렬·판정을 재현 가능한 규칙으로 실행 |

> WorkShield의 출력은 법률 자문, 위법·합법 판단, 유·불리 판정이 아닌 **표준 대비 검토 후보**입니다.

## 어떻게 사용하나요?

1. `assess_contract_scope`가 문서의 지원 범위와 비교할 계약 유형 후보를 점검합니다.
2. 사용자가 비교 기준을 확인하면 `review_contract`가 전체 계약서를 조항별로 검토합니다.
3. 클라이언트는 사용자 조항, 표준조항, 주의 문구 신호와 법령 원문을 RAG 컨텍스트로 활용합니다.

```text
계약서 입력
    ↓
지원 범위·비교 유형 확인
    ↓
조항 분리 → 표준조항 검색·재정렬 → 조항별 상태 분류
    ↓
계약서 전체의 누락 가능성·주의 문구 신호 확인
    ↓
표준조항·관련 법령 원문이 포함된 MCP 응답
```

## 실제 검토 예시

팀이 제작한 합성 SW 프리랜서 계약서
[`02_SW프리랜서용역계약서_EXTRA_NOMATCH강조형.pdf`](quality/fixtures/track_b/golden_b/raw/02_SW%ED%94%84%EB%A6%AC%EB%9E%9C%EC%84%9C%EC%9A%A9%EC%97%AD%EA%B3%84%EC%95%BD%EC%84%9C_EXTRA_NOMATCH%EA%B0%95%EC%A1%B0%ED%98%95.pdf)을
`SW_FREELANCE` 표준계약서와 비교했습니다. 아래는 2026-07-13 현재 `prod` 구성에서 **실제
`review_contract`를 실행한 결과**입니다.

| 항목 | 실행 결과 |
| --- | ---: |
| 응답 상태 | `OK` |
| 파싱된 사용자 조항 | 17건 |
| 표준 대응 후보 `NONE` | 5건 |
| 별도 확인 후보 `EXTRA` | 12건 |
| 검색 후보 없음 `NO_MATCH` | 0건 |
| 누락 가능성 `MISSING` | 18건 |
| 총 결과 | 35건 |
| 주의 문구 신호가 발견된 사용자 조항 | 4건 |

<details>
<summary><strong>입력 계약서의 대표 조항 보기</strong></summary>

```text
제11조(산출물의 저작권 등 귀속)
본 계약의 이행으로 발생하는 산출물에 대한 저작권 및 일체의 지식재산권은 대금 지급 여부와 관계없이
“갑”에게 귀속되며, “갑”은 이를 자유롭게 수정·복제·배포할 수 있다.

제12조(업무범위의 변경)
“갑”은 업무상 필요에 따라 과업의 범위를 변경할 수 있으며, “을”은 특별한 사유가 없는 한 이에 협조하여야 한다.

제13조(비밀유지)
“을”은 본 계약과 관련하여 취득한 “갑”의 영업비밀 및 기술정보 등 일체의 비밀정보를 계약기간은 물론
계약 종료 후에도 영구적으로 제3자에게 누설하거나 본 계약 목적 외로 사용하여서는 아니 된다.
```

전체 입력은 [예시 PDF](quality/fixtures/track_b/golden_b/raw/02_SW%ED%94%84%EB%A6%AC%EB%9E%9C%EC%84%9C%EC%9A%A9%EC%97%AD%EA%B3%84%EC%95%BD%EC%84%9C_EXTRA_NOMATCH%EA%B0%95%EC%A1%B0%ED%98%95.pdf)에서
확인할 수 있습니다.

</details>

<details>
<summary><strong><code>review_contract</code> 실제 응답의 대표 결과 보기</strong></summary>

아래 JSON은 35건의 실제 응답 중 `NONE`, `EXTRA`, `MISSING`의 대표 1건씩에서 주요 필드만
발췌한 것입니다. 표준조항과 법령 원문의 전체 본문은 가독성을 위해 생략했습니다.

```json
{
  "status": "OK",
  "contract_type": "SW_FREELANCE",
  "results": [
    {
      "user_clause": "제11조 (산출물의 저작권 등 귀속) ...",
      "matched_standard": {
        "clause_id": "sw_freelance-2020-art20",
        "title": "지식재산권의 귀속",
        "category": "IP_OWNERSHIP"
      },
      "deviation": "NONE",
      "confidence": 0.9836066961288452,
      "toxic_patterns": ["IP_TOTAL_FREE"]
    },
    {
      "user_clause": "제12조 (업무범위의 변경) ...",
      "matched_standard": {
        "clause_id": "sw_freelance-2020-art4",
        "title": "업무의 범위",
        "category": "SCOPE_SOW"
      },
      "deviation": "EXTRA",
      "confidence": 0.06068466231226921,
      "toxic_patterns": []
    },
    {
      "user_clause": "",
      "matched_standard": {
        "clause_id": "sw_freelance-2020-art1",
        "title": "기본원칙",
        "category": "GENERAL"
      },
      "deviation": "MISSING",
      "confidence": 0.0,
      "toxic_patterns": []
    }
  ]
}
```

`NONE`과 `toxic_patterns`가 함께 나올 수 있는 것처럼, 표준조항 대응 상태와 주의 문구 유사 신호는
서로 독립적으로 해석해야 합니다.

</details>

검색 인덱스·모델·표준 코퍼스가 바뀌면 예시 결과도 바뀔 수 있습니다. 예시의 신호는 실제
파이프라인 출력이지만 법률적 결론은 아닙니다.

## 결과를 어떻게 읽나요?

| 사용자용 표현 | MCP 값 | 의미 |
| --- | --- | --- |
| 표준 대응 후보 있음 | `NONE` | 사용자 조항이 임계값 이상의 표준조항과 잠정 매칭됨 |
| 별도 확인 필요 | `EXTRA` | 근접 표준조항은 있지만 매칭 임계값에 미치지 못함 |
| 검색 후보 없음 | `NO_MATCH` | 사용자 조항에 대해 비교할 표준조항 후보가 검색되지 않음 |
| 표준조항 누락 가능성 | `MISSING` | 표준계약서의 조항이 사용자 계약서 전체에서 대응되지 않음 |

`NO_MATCH`와 `MISSING`은 비교 방향이 다릅니다.

```text
사용자 계약서의 조항 → 표준조항 후보를 찾지 못함 = NO_MATCH
표준계약서의 조항 → 사용자 계약서 전체에서 대응 조항을 찾지 못함 = MISSING
```

예를 들어 사용자 계약서의 특수한 사내 행사 참여 조항에 비교할 표준 후보가 하나도 없다면
`NO_MATCH`입니다. 반대로 표준계약서에는 “재하도급 금지”가 있지만 사용자 계약서 전체에서 대응
조항을 찾지 못했다면 `MISSING`입니다.

## 주의 문구 유사 신호

WorkShield는 표준계약서 비교와 별도로, 과도한 경업금지·지식재산권 무상 귀속·일방적 업무 변경 등
알려진 주의 문구와 유사한 표현을 `toxic_patterns`에 표시합니다. 표준조항에 대응하는 조항에도
주의 문구 신호가 함께 나올 수 있습니다.

이 신호는 알려진 예문과의 유사성을 이용한 **추가 검토 후보**입니다. 신호가 있어도 위법·불공정을
확정하지 않으며, `toxic_patterns=[]`도 계약이 안전하다는 뜻이 아닙니다. 현재 성능과 한계는
[v5 품질 리뷰](docs/quality/v5_review.md)에서 확인할 수 있습니다.

## 핵심 특징

- **재현 가능한 검토:** 동일한 입력과 인덱스에는 동일한 결과를 반환합니다.
- **조항 단위 근거:** 사용자 조항, 대응 표준조항, 매칭 점수를 함께 제공합니다.
- **명시적인 상태:** 빈 응답으로 실패를 숨기지 않고 `NO_MATCH`, `EMPTY_DOCUMENT`, `PIPELINE_ERROR` 등으로 구분합니다.
- **계약 유형별 비교:** 서로 다른 표준계약서 코퍼스를 분리해 검색합니다.
- **법령 원문 연결:** 관련 법령 원문을 참고자료로 제공하되 법률 해석을 덧붙이지 않습니다.
- **MCP 조합성:** 전체 계약 검토, 단일 조항 검색·분류, 표준조항·법령 원문 조회를 독립적으로 사용할 수 있습니다.

## 아키텍처

핵심 판정 규칙과 외부 I/O를 분리한 헥사고날 구조입니다. `src/app.py`가 계약 검토 도구,
표준조항 리소스와 법령 프록시를 하나의 FastMCP 앱으로 조립합니다. 운영 환경의 임베딩·재정렬
연산은 RunPod Serverless GPU worker에 위임합니다. 자세한 구조와 데이터 흐름은
[아키텍처 문서](docs/architecture.md)를 참고하세요.

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

### Docker

```bash
just docker-build
```

Docker 배포는 MCP 서버 단일 컨테이너만 지원하며, streamable HTTP endpoint는
`http://localhost:8000/mcp`입니다.

## MCP 도구와 리소스

| 도구 | 역할 |
| --- | --- |
| `assess_contract_scope` | 지원 범위와 계약 유형 후보 점검 |
| `review_contract` | 계약서 전체의 조항 대응·누락·주의 문구·근거 조회 |
| `parse_contract` | 계약서를 조항 목록으로 분리 |
| `match_clause` / `classify_clause` | 단일 조항 검색·분류 |
| `get_grounding` | 카테고리 또는 조항과 관련된 법령 원문 조회 |
| `list_*` | 지원 계약 유형·카테고리·주의 문구 유형 조회 |

계약 유형 확인 순서, 상태별 클라이언트 처리와 전체 도구·리소스 목록은
[MCP 통합 가이드](src/server/README.md)를 참고하세요.

## 품질 기준

현재 활성 회귀 기준은 SI·SM·SW 유형별 45건, 총 **v5 골든 135건**입니다. 이 기준은
`NONE`과 `EXTRA` 조항 분류를 대상으로 하며, 문서 파싱·`MISSING`·법령 적용성까지 포함한
종합적 법률 품질 지표가 아닙니다.

| 계약 유형 | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| SI 하도급 | 0.700 | 0.933 | 0.800 |
| SM 하도급 | 0.735 | 0.833 | 0.781 |
| SW 프리랜서 | 0.842 | 0.533 | 0.653 |
| 전체 | 0.742 | 0.767 | 0.754 |

동결 수치와 평가 범위는 [v5 품질 기준선](docs/quality/baseline-v5.md), 현재 상태는
[START_HERE](docs/START_HERE.md)에서 확인할 수 있습니다.

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
    <td>데이터 임베딩,<br>주의 문구 패턴 수집·정의</td>
    <td>시스템 설계·<br>MCP 구현</td>
    <td>품질 평가·<br>테스트 계획</td>
    <td>데이터 전처리·<br>조항 카테고리 라벨링</td>
    <td>검색 파이프라인 구현</td>
  </tr>
</table>

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
