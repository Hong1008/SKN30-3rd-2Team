# 실험 C — v5 SW OVER_MATCH 단일 가설 검증

## 범위와 동결 기준선

이 실험은 `SW_FREELANCE` 45건만 대상으로 한다. 기준선은 `match_threshold=0.50`,
TP=16, FP=3, FN=14, TN=12, F1=0.653이다. 오류 표본은
`gold_deviation=EXTRA`이고 `predicted_deviation=NONE`인 행만 `OVER_MATCH`로 분류한다.
기준선 파일·case matrix·held-out manifest·진단·기준선 커밋의 SHA-256은
[`baseline.json`](../experiments/C/baseline.json)에 동결했다.

v5 SW case matrix의 10개 tuning topic group(30건)과 5개 held-out topic group(15건)을
사용한다. 공통 거버넌스가 topic group이 split을 가로지르는 누출을 거부한다.

## tuning 진단과 승인 경계

tuning 결과의 OVER_MATCH만 [`C_overmatch_taxonomy.md`](../experiments/C/C_overmatch_taxonomy.md)에
기록한다. 진단 축은 `contrast_clause_id`, top-1/top-2 점수 차, `trap`, 후보 출처(부모/서브청크),
topic group을 포함한다. 이 문서의 원인 선택과 구현 변경은 사람이 승인하기 전에는 수행하지 않는다.

후보 변경은 코퍼스·검색·리랭커·판정 중 정확히 하나의 레이어로 제한한다. 전역 threshold,
SI/SM 동작, `matched_standard`의 최고 후보 의미, `confidence`의 정규화된 리랭커 점수 의미는
변경하지 않는다. MCP 계약과 1차 LLM 무호출도 회귀 검증 대상이다.

사전 통과 기준은 tuning에서 FN 8 이하(기준선 대비 2건 이상 감소), FP 2 이하, F1 0.653 초과다.
held-out 채택 기준은 FN 3 이하, FP 1 이하, F1 0.653 초과다. 실행 후 기준을 바꾸지 않는다.

## 실행 게이트

```bash
PYTHONPATH=src python -m eval.run_eval --experiment=C --split=tuning
PYTHONPATH=src python -m eval.run_eval --experiment=C --split=held-out --approval-file=docs/experiments/C/approval.json
```

held-out은 `--case-ids`를 허용하지 않는다. tuning 통과 JSON, 승인 파일 해시, 코드 커밋,
manifest와 matrix 해시, git 추적·clean worktree, 원자적 `heldout-run.json` 선점이 모두 필요하다.
실패 기록도 보존되어 재실행을 막는다. 결과에는 before/after 혼동행렬, top-3 후보 및 점수 diff를 남긴다.

최종 결정은 `채택`(held-out 기준 충족), `보류`(개선이나 기준 미달/해석 모호), `폐기`(FN 개선 실패,
FP 악화, 또는 held-out 후 가설 변경 요구) 중 하나다. 실제 결과가 없으므로 현재 상태는 `평가 전`이다.
