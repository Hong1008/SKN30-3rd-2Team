# 작업 분배 (Task Cards)

WorkShield 작업 카드 색인입니다. 상태 기준은 **2026-07-10 결정 로그와 현재 구현**입니다.

> 기준: [2026-07-10 결정 로그](../dicision/07-10.md). `X_graph.md`와 `Z_Lever.md`는 기각·제외된
> 과거 제안으로 현재 진행 대상에 포함하지 않습니다. 카드 본문의 오래된 설계는 이력으로 보존하며,
> 아래 표의 현재 상태를 우선합니다.

> [!WARNING]
> **v4 골든셋 한계 및 주의**
> v4 골든셋은 **독소 조항에 대한 hard-negative challenge set**으로 구성되어 있습니다. SI 및 SW 계약 유형에는 이탈 양성(EXTRA 등) 케이스가 존재하지 않으므로, **이탈 검증(성능 비교 및 튜닝) 용도로 부적합**하며 이를 기준으로 이탈 임계값이나 모델 구성을 튜닝해서는 안 됩니다.

## 현재 진행 현황 (2026-07-12 정리)

| 카드 | 현재 상태 | 다음 처리 |
| --- | --- | --- |
| A · B · C | ✅ 1차 MVP 완료·통합 검증 | 운영 요구가 생길 때만 후속 분리 |
| D | ✅ 평가 하니스·Track A/B·실측 완료 | case-level 진단 덤프 완료 및 v4/v5 정합성 대조 지원 |
| E | ✅ 독소 인덱스·검색·결과 배선·골든 평가 완료 | N 후속 진단/개선에서 다룸 |
| G | ✅ 서브청크·부모 roll-up 완료 | 삭제 탐지는 현 판정 구조에 맞춰 재설계할 때만 진행 |
| H | 🗃️ 폐기(현 상태로 수행 금지) | 제거된 `CHANGED`·`uncovered_sub_chunk_ids` 전제의 과거 설계 |
| I | ✅ 구현·검증 완료 | 과거 승인 게이트는 이력으로만 보존 |
| J | ✅ 완료 | 현재 NONE/EXTRA 1차 판정의 기준 |
| K | ⏸️ 2차 트랙 backlog | structured schema·모델 사인오프 후 착수 |
| L | ✅ v3 117건·held-out 완료 | 독소 양성 확대는 v4 별도 후속 |
| M | ⏸️ K 이후 재검토 | K 출력 계약 전 평가 구현은 진행하지 않음 |
| N | ✅ 코퍼스 40→90·재측정 완료 | case-level 분석을 바탕으로 개선안 별도 카드화·사인오프 |
| O | ✅ 정적 계약유형 grounding·캐시·상한 완료 | 동적 질의/버전별 매핑은 현재 범위 밖 |
| P · Q | ✅ 완료·재검증 | 현 정책 유지 |

## 공통 작업 흐름 (TDD)
1. 내 카드의 **통과할 테스트 파일**을 먼저 읽는다 (= 무엇을 만들지가 거기 적혀 있음).
2. 그 파일 맨 위 `pytestmark = pytest.mark.skip(...)` **한 줄을 삭제**한다 → 빨강(실패) 확인.
3. 대상 모듈(스켈레톤 파일)의 `raise NotImplementedError` 를 **실제 구현으로 교체**한다.
4. `uv run pytest <내 테스트 경로>` 가 **초록(통과)** 이 될 때까지 반복한다.
5. 전체 `uv run pytest` 가 깨지지 않는지 확인하고 커밋/PR.

> 작업 전 [AGENTS.md](../../AGENTS.md) 와 본인 모듈 폴더의 `README.md` 를 반드시 읽으세요.
> 동결 계약(`src/contracts/`)·MCP 시그니처를 바꿔야 하면 **먼저 PM/리드와 합의**.

## 담당 & 의존성

| 담당 | 카드 | 모듈 | 선행(실제 데이터 통합 시) |
| --- | --- | --- | --- |
| 팀원 A | [A_normalize.md](A_normalize.md) | `pipe/normalize` + `03_normalized` 정답 데이터 | 02_converted (있음) |
| 팀원 B | [B_index.md](B_index.md) | `pipe/build_index` | A의 03_normalized |
| 팀원 C | [C_review_pipe.md](C_review_pipe.md) | `pipe/review_pipe` (review_contract) | B의 인덱스 |
| 팀원 D | [D_eval.md](D_eval.md) | `eval/metrics·run_eval·ablation` + 골든셋 | (집계는 독립) |
| 리드 | — | `mcp_server` + `demo` | C의 review_contract |

## 🚀 고도화 트랙 (코어 안정화 후 얹음)

> 기획서 7.1·7.2 / 10장 — **코어(A·B·C·D)가 도는 것을 확인한 뒤** 착수합니다. 포트폴리오 차별점이지만
> 동시 착수 시 코어 명제가 흐려지므로 **여유 팀원 또는 코어 완료자**가 맡습니다. enum·모델·DB·순수함수는 이미 준비됨.

| 카드 | 모듈 | 선행 | 난이도 |
| --- | --- | --- | --- |
| [E_toxic.md](E_toxic.md) | 독소조항 양방향 검색 (`toxic` 컬렉션 + 매칭) | B 인덱스 패턴 | 중 |
| [G_sub_chunk.md](G_sub_chunk.md) | 거대 조항 서브청킹 + Max roll-up 검색 | B 인덱스 패턴 | 상 |
| [H_check_coverage.md](H_check_coverage.md) | 과거 항 단위 삭제 탐지 설계 — **폐기** | — | — |
| [I_progress.md](I_progress.md) | `review_contract` 진행률 알림 — **완료** | C review 흐름 | 중 |

> 위 표는 과거 고도화 분류를 보존한 것입니다. 현재 상태는 문서 상단 진행 현황을 우선합니다.

## 🔧 재설계 트랙 (07-07 세션 — NONE/CHANGED 판정 아키텍처)

> 근거: [07-03 결정 로그](../dicision/07-03.md) — 규칙기반(정규식) 치명변경 탐지가 구조적으로
> 의미동치성을 못 잰다는 게 실측으로 확인돼, 1차(결정론)/2차(LLM, 서버 밖) 판정 경계를 재설계.
> J→K, J·K→M 순서로 의존, L·N은 독립적으로 병행 가능.

| 카드 | 내용 | 선행 |
| --- | --- | --- |
| [J_deviation_redesign.md](J_deviation_redesign.md) | 규칙기반 치명변경 탐지·difflib 폴백 제거, 커버리지 미달→CHANGED 확정 / 충족→잠정 NONE 재정의 | 없음 |
| [K_second_stage_llm.md](K_second_stage_llm.md) | 잠정 NONE의 의미동치성 최종 확인 (서버 밖 LLM) | J |
| [L_golden_v3.md](L_golden_v3.md) | 골든셋 v3 — 조 전체 단위 SI·SM 확장 (SW 파일럿 17건 완료) | 없음 |
| [M_eval_dual_track.md](M_eval_dual_track.md) | eval 1차/2차 분리 채점 + 결정론 규칙(#5) 공존 설계 | J, K |
| [N_toxic_corpus_bias.md](N_toxic_corpus_bias.md) | 독소 탐지 recall 붕괴 — 코퍼스 당사자 어휘 편중(SW 전용 → SI/SM 붕괴) | 없음(독립) |
| [O_grounding_contract_type.md](O_grounding_contract_type.md) | Grounder 계약유형별 법령 그라운딩(하도급법 미반영) | 없음(독립) |
| [P_text_normalization.md](P_text_normalization.md) | 검색·리랭킹 입력 텍스트 정규화 — 마크다운 헤더/특수문자 비대칭이 독소 검색을 붕괴시킴 | 없음(독립, N의 recall 검증은 이 카드 선행 필요) |
| [Q_standard_version_scoping.md](Q_standard_version_scoping.md) | 표준조항 검색 풀에 신구 버전(2022/2025) 혼재 — `version` 스코핑 자체가 미설계 | 없음(독립) |

## 과거 초기 병렬화 안내 (완료 이력)
테스트가 **fake 주입 / 순수 입력** 기반이라, 실제 인덱스·데이터 없이도 구현·통과가 가능합니다.
- A: 02_converted 마크다운만 있으면 시작 (있음)
- C: 테스트가 fake retriever/grounder 를 주입 → B의 실제 인덱스 없이 review_contract 구현 가능
- D: metrics·run_eval·ablation 순수 함수는 의존성 0 → 즉시 시작
- B: A의 03_normalized 가 있어야 실제 빌드가 의미 있음 (그 전엔 시드 3건으로 테스트 가능)

**실제 데이터 통합**(전체 코퍼스로 빌드→검색→평가)만 위 선행 순서를 따릅니다.

## 테스트 확인
```
uv run pytest -ra        # skip 목록으로 남은 규격 확인
uv run pytest -q         # 전체 통과/스킵 요약
```
