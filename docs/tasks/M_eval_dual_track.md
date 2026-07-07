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

## 참고
- [src/eval/run_eval.py](../../src/eval/run_eval.py) `deviation_scores`·`degeneracy_alerts`·`_coverage_cell`
- [src/eval/README.md](../../src/eval/README.md) — LLM-judge 금지 규칙 원문 맥락
- [J_deviation_redesign.md](J_deviation_redesign.md)·[K_second_stage_llm.md](K_second_stage_llm.md)
