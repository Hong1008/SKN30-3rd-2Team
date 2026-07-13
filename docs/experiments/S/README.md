# 실험 S 산출물

이 디렉터리는 실험 S 전용이다. 기존 `src/eval/golden/v4_result.md`와 v4 진단 파일은 수정하지 않는다.

- `approval.json`: tuning 통과 후 사람이 작성·커밋하는 승인 파일 (`approval.example.json` 참고)
- `tuning-result.json` / `.md`: 36건 tuning 결과
- `heldout-result.json` / `.md`: 승인된 18건 결과
- `heldout-run.json`: 성공한 held-out 실행의 단회 불변 기록

## 2026-07-13 tuning 판정

실험 S의 제목 접두 후보는 tuning 36건에서 기준을 충족하지 못해 **폐기**했다.

| 구분 | TP | FP | FN | TN | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 기준선 | 9 | 5 | 9 | 13 | 0.563 |
| 후보 | 6 | 2 | 12 | 16 | 0.462 |

- FN 통과 기준(7 이하)과 F1 통과 기준(0.563 초과)을 모두 충족하지 못했다.
- `heldout-result.*`, `heldout-run.json`, `approval.json`은 만들지 않는다. 동결 held-out은 소비하지 않는다.
- `tuning-result.*` 및 같은 실행에서 생성된 `v4_result.*`·`v4_diagnostics.*`는 폐기 근거로 보존한다.

재현 명령:

```bash
just eval-s tuning prod
just eval-s held-out prod docs/experiments/S/approval.json
```

운영 순서는 반드시 다음과 같다.

1. 거버넌스 구현 변경을 먼저 커밋한다.
2. clean 상태에서 `just eval-s tuning prod`를 실행한다.
3. tuning이 통과한 경우에만 생성된 `tuning-result.*`와 사람이 작성한 `approval.json`을 함께 커밋한다.
4. clean 상태를 확인한 뒤 held-out 명령을 실행한다.

`tuning` 실행은 결과 파일을 생성해 작업 트리를 변경한다. 따라서 tuning 직후 승인 파일만
작성하고 커밋하지 않은 상태에서는 held-out이 의도대로 차단된다.

held-out은 tuning 통과, 승인 파일의 manifest·tuning 결과·코드 식별자·기준선 커밋 일치,
승인 파일의 git 추적·커밋 및 clean worktree, 기존 실행 기록 부재, 쓰기 모드가 모두 충족될 때만
실행된다. 실행 직전에 `heldout-run.json`을 `STARTED`로 원자 예약하며, 실패도 `FAILED`로 남겨
재실행을 차단하고 성공 시 `SUCCEEDED`로 갱신한다.
