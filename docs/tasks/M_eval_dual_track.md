# [재설계 M] eval — 1차/2차 분리 채점 + 결정론 규칙(#5)과의 공존

> 근거: [07-03 결정 로그](../dicision/07-03.md) §3 미해결항목, 07-07 세션(1차/2차 판정 경계 설계).
> 선행: [J_deviation_redesign.md](J_deviation_redesign.md)(1차 동작 확정), [K_second_stage_llm.md](K_second_stage_llm.md)(2차 존재).
> 이 카드는 **설계 질문 목록만 정리** — 해결책은 착수 세션에서 결정.

## 배경

J로 인해 `review_contract`의 `deviation`이 "최종 판정"에서 "1차 잠정치(CHANGED만 확정, NONE은
잠정)"로 의미가 바뀐다. 그런데 지금 [run_eval.py](../../src/eval/run_eval.py)의 `deviation_scores`는
`deviation != Deviation.NONE`을 그대로 이탈 예측으로 써서 `gold_deviation != "NONE"`과 비교한다 —
이 비교가 **무엇을 재는 지표인지** J 이후엔 재정의가 필요하다. 또한 AGENTS.md 규칙 #5
("평가에 LLM-judge 금지")가 있는데, 2차 자체가 LLM이라 **2차의 정확도를 어떻게 결정론적으로
검증할지**가 정면 과제다.

## 풀어야 할 질문 (해결책 아님 — 착수 세션이 답할 것)

1. **1차만 채점할 때 "이탈 P/R"이 뭘 의미해야 하는가?**
   J 이후 1차가 확정하는 건 CHANGED(커버리지 미달)뿐이므로, 후보案: "CHANGED로 확정한 것 중
   `gold_deviation != NONE`인 비율"(precision)과 "`gold_deviation != NONE`인 골든 중 1차가 실제로
   CHANGED 확정한 비율"(recall, 나머지는 잠정 NONE으로 2차에 위임됨을 인정) — 이게 맞는 지표
   설계인지, 아니면 완전히 다른 축(예: "잠정 NONE 중 2차가 필요한 비율", 즉 얼마나 많은 케이스가
   1차만으론 결론이 안 나는지를 노출하는 지표)이 더 유용한지.

2. **2차(LLM) 정확도는 무엇으로, 어떻게 검증하는가?**
   AGENTS.md 규칙 #5는 "평가에 LLM-judge 금지"인데, 이건 "LLM이 채점자가 되는 것"(예: GPT가
   시스템 출력을 보고 좋다/나쁘다 평가)을 금지하는 취지였다. 2차는 **시스템의 판정 로직 자체가
   LLM**이므로 "LLM-judge로 평가"와는 다른 문제 — 2차의 최종 NONE/CHANGED 출력을 **골든 정답과
   결정론적으로(문자열/값 비교)** 대조하는 건 규칙 #5 위반이 아닐 가능성이 높다(판단 근거: 비교
   자체는 정확한 값 매칭이지 LLM이 채점하는 게 아님). 이 해석이 맞는지 확인하고, 맞다면:
   - 매 실행마다 실제 LLM을 호출해 골든 87건을 채점하는 게 비용·재현성(같은 프롬프트가 매번
     같은 답을 낸다는 보장 없음) 측면에서 타당한지, 아니면 **고정 스냅샷 회귀**(한 번 실행한
     2차 출력을 버전 관리해두고 그 스냅샷과 diff)가 나은지.

3. **트랙 B(실계약 M:N 커버리지)는 어떻게 되는가?**
   트랙 B는 애초에 라벨 없는 커버리지 지표라 NONE/CHANGED 최종판정과 무관해 보이지만,
   `_coverage_cell`의 `deviation_dist`(분포 집계)가 이제 "잠정 NONE 다수"로 쏠릴 가능성이 있다 —
   이게 축퇴 경보(`coverage_degeneracy_alert`)를 오작동시키는지 확인 필요.

4. **`degeneracy_alerts`(전부 양성/음성 축퇴 경보)의 의미 재검토**
   1차만 볼 때 "전부 잠정 NONE"이 정상적으로 늘어날 수 있는데(J의 의도된 결과), 이걸 v1/v2에서
   쓰던 것과 같은 문구("축퇴 의심")로 경보하면 오해를 부른다 — 문구·임계 재검토 필요.

## 완료 조건 (DoD) — 이 카드는 "질문에 답하는 설계 문서"까지가 완료
- [ ] 위 질문 1~4에 대한 결정(사람 사인오프 포함, AGENTS.md §2)
- [ ] 결정 사항을 [D_eval.md](D_eval.md)·[eval/README.md](../../src/eval/README.md)에 반영
- [ ] 실제 지표 코드 변경(`run_eval.py`)은 **별도 후속 카드**로 분리(이 카드 범위 아님)

## 5. Hybrid 검색 RRF 융합 가중치(dense:BM25) 스윕

> 배경: `v3_result.md`에서 `bm25` recall@5=0.880 < `dense`=0.920인데, 동일가중 `hybrid`=0.893으로
> **dense 단독보다 낮음** — 조항 매칭은 어휘가 계약유형별로 계속 바뀌는(도급인/원사업자 등)
> 패러프레이즈 도메인이라 BM25가 구조적으로 약한데, `_reciprocal_rank_fusion`(RRF)이 두 리스트를
> 동일 가중치로 합산해 약한 쪽이 강한 쪽 후보를 top_k 밖으로 밀어내는 것으로 보인다.
> (`hybrid_rerank`=0.920로 dense와 동률 회복하지만, 이는 최종 매칭이 `fusion_score`가 아니라
> `rerank_score`만 쓰기 때문 — 가중치 조절의 이득은 "reranker에 어떤 후보가 올라가는지"(pre-rerank
> recall)에 국한되며, dense를 능가하기보다 동일가중 hybrid의 손실을 없애는 효과에 가까울 수 있다.)

- [x] **가중치 파라미터화 구현 완료** — `_reciprocal_rank_fusion`·`hybrid_search`·`hybrid_search_many`
      ([vector_manager.py](../../src/adapter/vector_manager.py))와 `Retriever` 포트
      ([adapter/port.py](../../src/adapter/port.py))에 `dense_weight`·`bm25_weight` 키워드 인자 추가
      (기본값 1.0/1.0 = 기존 동일가중 RRF와 동일, 하위호환). `review_contract`/`review_pipe.py`에는
      아직 배선하지 않음 — 최적 비율이 정해지기 전에 프로덕션 경로에 넣는 건 시기상조로 판단.
- [ ] **비율 스윕 실행** — `build_cases_by_variant`([run_eval.py:195](../../src/eval/run_eval.py#L195))의
      `vector.hybrid_search_many(...)` 호출에 `dense_weight`/`bm25_weight`를 넘겨 여러 비율(예: 5:5,
      7:3, 8:2, 9:1, dense 100%)로 `hybrid`·`hybrid_rerank` 지표를 재계산 → 어느 비율이 dense 단독
      recall@5(0.920)을 실제로 능가하는지, 아니면 손실만 없애는 수준인지 확인.
- [ ] **held-out 검증** — 스윕에 쓴 골든셋과 최종 채택 비율을 검증할 골든셋을 분리한다(v3 자체에
      과적합된 매직넘버 방지 — eval-run-ownership-and-none-definition 메모의 "임계값은 held-out으로만
      보정" 원칙과 동일 근거).
- [ ] **채택 여부 사인오프** — 스윕 결과 유의미한 개선이 있으면 `review_contract` 기본값에 반영할지
      사람이 결정(AGENTS.md §2). 개선이 없으면 "동일가중 유지" 결정도 기록.

## 참고
- [src/eval/run_eval.py](../../src/eval/run_eval.py) `deviation_scores`·`degeneracy_alerts`·`_coverage_cell`·`build_cases_by_variant`
- [src/adapter/vector_manager.py](../../src/adapter/vector_manager.py) `_reciprocal_rank_fusion`
- [src/eval/README.md](../../src/eval/README.md) — LLM-judge 금지 규칙 원문 맥락
- [J_deviation_redesign.md](J_deviation_redesign.md)·[K_second_stage_llm.md](K_second_stage_llm.md)
- [src/eval/golden/v3_result.md](../../src/eval/golden/v3_result.md) — 스윕 배경이 된 4변형 비교 수치
