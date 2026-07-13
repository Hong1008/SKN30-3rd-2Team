# 실험 C 산출물

v5 SW OVER_MATCH 개선 실험의 동결 입력, 후보 승인, tuning/held-out 결과를 둡니다.

- `baseline.json`: 기준선과 입력 해시
- `C_overmatch_taxonomy.md`: tuning OVER_MATCH 분류
- `C_candidate_comparison.md`: tuning OVER_MATCH의 표준 조항·서브청크 부모 후보 비교
- `C_source_agreement.md`: tuning 전체에서 출처 불일치 규칙의 부작용을 확인하는 비교표
- `approval.example.json`: 사람 승인 파일 형식
- `tuning-result.*`, `heldout-result.*`, `heldout-run.json`: 실행 산출물

## 현재 준비 상태

- v5 SW 45건의 기준선과 입력 해시는 `baseline.json`으로 동결했다.
- tuning 30건의 OVER_MATCH 10건은 `C_overmatch_taxonomy.md`에 기록했다.
- 후보 C1을 구현했다: 표준 조항 최고 후보와 서브청크 roll-up 부모 후보가 서로 다르면, 최고
  후보는 보존한 채 `EXTRA` 검토 후보로 보수 처리한다.
- C1은 tuning의 `v5-sw-07`·`v5-sw-28` FN을 줄이고, 이미 EXTRA인 `v5-sw-08`에는 영향을 주지
  않는다는 counterfactual을 근거로 선정했다. 실제 효과는 tuning 실행으로만 판정한다.

taxonomy에서 서브청크 승자가 6건, 표준 조항 승자가 4건이고 trap도 분산돼 있다. 이 분포만으로
서브청크 제거·임계값 변경·특정 trap 규칙 중 하나를 선택할 근거는 충분하지 않다.

## 다음 승인 단위

후보 구현 전 tuning 전용 진단으로 각 OVER_MATCH에 다음을 함께 기록한다.

- 표준 조항과 서브청크 부모의 최고 rerank 점수 및 각각의 부모 clause ID
- 두 후보가 같은 부모를 가리키는지 여부
- 승자 교체가 기준선의 TP/FN에 미칠 예상 방향

이 진단을 바탕으로 **한 가지 메커니즘만** 선택해 구현한다. 현재 선택된 C1 외의 규칙·임계값은
이번 tuning에서 바꾸지 않는다. held-out 케이스나 held-out 진단은 후보 선택에 사용하지 않는다.

1·2번 비교표는 모델 평가를 다시 실행하지 않고 동결된 v5 tuning 진단에서 만든다.

```bash
just prepare-c
```

3번(예상 TP/FN 방향)은 이 두 표에서 선택한 **하나의 후보 규칙**을 tuning 전체에 적용해
계산한다. C1 구현 커밋과 clean worktree를 확인한 뒤 `just eval-c tuning prod`를 실행한다.

## 실행 순서

후보 변경을 커밋한 뒤 clean worktree에서 실행한다.

```bash
just eval-c tuning prod
# tuning 통과 + approval.json 커밋 후에만
just eval-c held-out prod docs/experiments/C/approval.json
```

held-out은 tuning 통과, 승인 파일의 input hash·코드 커밋 일치, clean worktree, 기존 실행 기록 부재를
모두 만족할 때만 실행된다. tuning 실패 시 held-out은 실행하지 않고 후보를 폐기하거나 새 실험 카드로 분리한다.
