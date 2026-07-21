# 도구와 워크플로우

## 전체 계약서 검토

1. `list_contract_types`를 호출해 허용된 `contract_type`을 읽는다.
2. 유형이 불확실하면 `assess_contract_scope`에 계약서를 전달한다.
3. `IN_SCOPE`이면 제안 유형을 기본값으로 제시하고, `CONTRACT_TYPE_UNCERTAIN`이면 사용자가 선택하게 한다. `OUT_OF_SCOPE`는 계속하기 전 재확인을 받는다. `EMPTY_DOCUMENT`면 검토를 호출하지 않는다.
4. 사용자가 선택한 유형과 같은 파일 입력으로 `review_contract`를 호출한다.

로컬 stdio의 예시는 다음과 같다.

```json
{
  "contract_type": "<list_contract_types의 값>",
  "file_path": "/absolute/path/to/contract.pdf"
}
```

streamable HTTP의 예시는 다음과 같다.

```json
{
  "contract_type": "<list_contract_types의 값>",
  "file_content": "<파일 바이트의 base64 문자열>",
  "file_name": "contract.pdf"
}
```

`file_path`와 `file_content`/`file_name` 조합은 함께 전달하지 않는다. 지원 형식은 HWP, HWPX, HWPML, PDF, XLS, XLSX, DOCX다.

## 부분 검토와 조회

| 목적 | 도구 또는 리소스 |
| --- | --- |
| 계약서를 조항으로 분리 | `parse_contract` |
| 유사 표준조항 후보만 조회 | `match_clause` |
| 한 조항의 표준 대비 상태 판정 | `classify_clause` |
| 전체 검토와 누락 후보 탐지 | `review_contract` |
| 계약 유형·카테고리·주의 패턴 조회 | `list_contract_types`, `list_categories`, `list_toxic_patterns`, `list_toxic_pattern_details` |
| 법령 원문 참고자료 조회 | `get_grounding` |
| 계약 유형별 표준조항 목록 | `standard://{contract_type}` |
| 특정 표준조항 원문 | `standard://{contract_type}/{clause_id}` |

`classify_clause`는 `MISSING`, `toxic_patterns`, 법령 근거를 만들지 않는다. 전체 문서의 누락 후보 또는 주의 문구 신호가 필요하면 `review_contract`를 사용한다.

`get_grounding`과 법령·판례 프록시 도구는 원문·검색 결과를 제공한다. 이를 근거로 법률 해석을 확정하지 않는다.
