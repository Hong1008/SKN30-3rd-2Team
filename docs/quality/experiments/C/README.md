# 실험 C 산출물

v5 SW OVER_MATCH 개선 실험의 동결 입력, 후보 승인, tuning/held-out 결과를 둡니다.

- `baseline.json`: 기준선과 입력 해시
- `C_overmatch_taxonomy.md`: tuning OVER_MATCH 분류
- `C_candidate_comparison.md`: tuning OVER_MATCH의 표준 조항·서브청크 부모 후보 비교
- `C_source_agreement.md`: tuning 전체에서 출처 불일치 규칙의 부작용을 확인하는 비교표
- `approval.example.json`: 사람 승인 파일 형식
- `tuning-result.*`, `heldout-result.*`, `heldout-run.json`: 실행 산출물

## C1 최종 상태

C1은 표준 조항 최고 후보와 서브청크 roll-up 부모 후보가 다를 때 `EXTRA` 검토 후보로 처리한
실험 규칙이었다. tuning은 통과했지만, 승인된 held-out에서 FP가 1건에서 2건으로 증가해 채택
기준을 충족하지 못했다. 따라서 **보류**이며 기본 런타임 동작에서 제거됐다.

held-out 단회 실행은 완료됐고, `heldout-run.json`이 `SUCCEEDED`인 동안 C tuning 재실행도
차단된다. 기존 결과를 덮어쓰거나 held-out 결과를 보고 C1을 조정하지 않는다. 후속 개선은 새
가설·새 실험 카드·새 독립 held-out으로 분리한다. 상세 판정은
`docs/decisions/07-13.md`의 “실험 C1 최종 판정”을 따른다.

taxonomy에서 서브청크 승자가 6건, 표준 조항 승자가 4건이고 trap도 분산돼 있었다. 이 분포만으로
서브청크 제거·임계값 변경·특정 trap 규칙 중 하나를 일반 규칙으로 채택할 근거는 충분하지 않았다.
