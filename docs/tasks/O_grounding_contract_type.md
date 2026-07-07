# [재설계 O] Grounder — 계약유형별 법령 그라운딩 쿼리

> 근거: 07-07 세션(사용자 문제 제기 + 코드 실측). J~N(NONE/CHANGED 판정 재설계)과 **독립적인 축**
> (검색·판정이 아니라 grounding 계층) — 선행 없음, 즉시 착수 가능.

## 배경 — 실측으로 확인된 결함

`Grounder.get_grounding`이 `category`만 받고 `contract_type`을 아예 못 받는 구조라, SI_SUBCONTRACT·
SM_SUBCONTRACT(하도급법 적용 대상)도 SW_FREELANCE와 똑같이 민법·저작권법 위주 쿼리를 받는다.

- **Protocol 자체에 구멍**: [contracts/ports.py:22](../../src/contracts/ports.py#L22)
  `get_grounding(self, category: Category)` — `contract_type` 인자 없음.
- **`CATEGORY_QUERIES`**([korean_law_grounder.py:10-21](../../src/contracts/implement/korean_law_grounder.py#L10-L21))는
  유형 무관 고정 딕셔너리이고, 매핑된 10개 전부 민법/저작권법/부정경쟁방지법/근로기준법 — 코드
  전체에 "하도급법" 언급 0건.
- **Category 15종 중 4종(`CONTRACT_PERIOD`·`DELIVERY_INSPECTION`·`WARRANTY`·`SUBCONTRACTING`)은
  아예 미매핑** → `"민법 도급"` 폴백. 실측(SI/SM 표준 코퍼스 카테고리 분포):

  | 카테고리 | SI 2025 | SM 2025 | 매핑 상태 |
  | --- | --- | --- | --- |
  | `SUBCONTRACTING`(재하도급) | 12건(최다) | 12건(최다) | ❌ 미매핑 |
  | `DELIVERY_INSPECTION`(납품/검수) | 10건 | 7건 | ❌ 미매핑 |
  | `WARRANTY`(하자담보) | 5건 | 6건 | ❌ 미매핑 |
  | `PAYMENT`(대금지급) | 6건 | 7건 | 🟡 매핑 있으나 SW용 고정("민법 제665조") |

  SI/SM에서 **가장 흔한 카테고리(재하도급)가 완전 미매핑** — 가장자리 케이스가 아니라 다수 조항에
  영향을 미치는 결함.
- **호출부 3곳 전부 `contract_type`을 스코프에 두고도 안 넘김**: [review_pipe.py](../../src/pipe/review_pipe.py)
  `_grounding_for`, [server.py:483](../../src/server/server.py#L483) `classify_clause`,
  [server.py:260](../../src/server/server.py#L260) 단독 `get_grounding` 도구.
- **eval에 안 잡힘**: `run_eval.py`가 드라이버 전체에서 `NullGrounder`(no-op)를 주입 — 이 결함은
  어떤 result.md에도 드러난 적 없고, 실제 MCP 서버/데모에서 SI·SM을 검토할 때만 나타난다.
- **선행 시도 흔적**: [Z_Lever.md:53,108](Z_Lever.md#L53)에 `grounding_ref`(예: "하도급법 제13조")
  아이디어가 있었으나, 항 단위 "법률 레버" 판정이라는 훨씬 큰 설계(오늘 세션에서 core/deviation.py
  삭제 대상이 된 부정어·숫자·당사자 규칙과 같은 축 + NLI)에 묶여 있었고 그 설계 전체가 문서 맨
  위에서 "오버엔지니어링"으로 이미 기각됨. 이 좁은 문제(카테고리+유형→쿼리) 자체는 단독으로
  다뤄진 적 없음.

## 확정된 설계 (07-07 세션)

- ✅ **`Grounder.get_grounding`에 `contract_type` 추가, 하위호환 유지**:
  `get_grounding(self, category: Category, contract_type: Optional[ContractType] = None) -> List[GroundingLaw]`.
  기존 호출부(있다면)는 `contract_type` 생략 시 지금과 동일하게 동작 — 가법적 확장, 07-01의
  `reranker`/`graph` 추가 패턴과 동일 원칙.
- ✅ **SW_FREELANCE 쿼리는 그대로 유지** — 사용자 판단(현재 `CATEGORY_QUERIES`가 이미 최적화됨).
  변경 대상은 SI_SUBCONTRACT·SM_SUBCONTRACT 오버라이드 추가뿐.
- ✅ **쿼리 테이블 구조: `(Category, ContractType)` 우선 조회 → 없으면 유형 무관 fallback**.
  즉 SI/SM에서 하도급법이 필요한 카테고리만 override 딕셔너리에 추가하고, 나머지는 기존
  `CATEGORY_QUERIES` 공용값을 그대로 씀(전체 재작성 아님, 최소 추가).
- ✅ **초기 매핑 후보 3건(사용자 제공, 초안 — 실제 반영 전 법률 검토 권장)**:

  | Category | ContractType | 쿼리(초안) |
  | --- | --- | --- |
  | `PAYMENT` | SI/SM | 하도급법 제13조(하도급대금의 지급 등) |
  | `DELIVERY_INSPECTION` | SI/SM | 하도급법 제9조(검사의 기준·방법 및 시기) |
  | `CONFIDENTIALITY` | SI/SM | 하도급법 제12조의3(기술자료 제공 요구 금지 등) — 부정경쟁방지법과 병기 검토 |

## 구현 대상

1. `contracts/ports.py`: `Grounder.get_grounding` 시그니처에 `contract_type: Optional[ContractType] = None` 추가.
2. `korean_law_grounder.py`: `CATEGORY_QUERIES`(유형 무관 공용) 옆에 `SUBCONTRACT_CATEGORY_QUERIES`
   같은 SI/SM 전용 override 딕셔너리 신설. `get_grounding`이 `contract_type`이 SI/SM이고 override에
   해당 카테고리가 있으면 그걸, 없으면 기존 공용 값을 쓰도록 조회 순서 구현.
3. 위 3건 초안 반영 + **나머지 미매핑/SW전용 카테고리의 SI·SM용 조문 확정**(핵심 산출물, 아래
   "미결정" 참조) — 최소한 `SUBCONTRACTING`(최빈값, 재하도급 관련이라 하도급법이 명백히 우선)만이라도.
4. 호출부 3곳(`review_pipe._grounding_for`, `server.py`의 `review_contract`·`classify_clause`·단독
   `get_grounding` 도구) 전부 `contract_type`을 실제로 넘기도록 수정.
5. `NullGrounder`(eval 드라이버)는 no-op이라 시그니처만 맞추면 됨 — 별도 로직 불필요.

## 미결정 / 사인오프 필요 (AGENTS.md §2)
- ✅ Protocol 확장 방식(가법·하위호환) — 07-07 세션 확정
- ✅ SW_FREELANCE 불변, SI/SM만 override — 07-07 세션 확정
- [ ] **`SUBCONTRACTING`·`WARRANTY`·`CONTRACT_PERIOD`(SI/SM 미매핑 잔여 3종)와 `TERMINATION`·`LIABILITY`·
      `DISPUTE`·`SCOPE_SOW`(SW 매핑이 SI/SM에도 맞는지 재검토 필요한 항목)의 정확한 하도급법 조문** —
      법률 검토 필요, 이 문서에서 추측으로 채우지 않음(사용자 제공 3건 외 전부 오픈).
- [ ] SI/SM이 각각 2022/2025 두 버전을 가진 것이 grounding 쿼리에도 버전 차이를 요구하는지
      (법 개정 시점과 표준계약서 개정 시점이 다를 수 있음) — 확인 필요.
- [ ] `query_law(clause_text)`(동적 질의 경로)도 같은 맹점 공유 — `contract_type` 없이 조항 본문만
      질의하므로 "이게 하도급 맥락"이라는 신호가 안 들어감. 이 경로도 `contract_type`을 받아
      질의 문자열에 힌트를 덧붙일지 여부 결정 필요(범위에 포함할지도 미결정).

## 완료 조건 (DoD)
- [ ] `Grounder.get_grounding` 시그니처 확장 + 호출부 3곳 전부 `contract_type` 전달
- [ ] SI/SM override 테이블에 최소 사용자 제공 3건 반영, 실제 `koreanLaw.query()` 호출 검증
- [ ] 위 "미결정" 법률 조문이 확정되는 대로 override 테이블 확장
- [ ] `uv run pytest tests/` 통과 (Grounder 관련 기존 테스트 갱신)
- [ ] LLM 호출 없음(규칙 #1 무관 — 이 계층은 애초에 결정론 쿼리 매핑) 재확인

## 참고
- [contracts/ports.py](../../src/contracts/ports.py) · [korean_law_grounder.py](../../src/contracts/implement/korean_law_grounder.py)
- [Z_Lever.md](Z_Lever.md) §5(`grounding_ref` 아이디어, 기각된 큰 설계 안의 파편)
- `.agents/skills/korean-law-mcp` — korean-law-mcp 쿼리 규격 참고
