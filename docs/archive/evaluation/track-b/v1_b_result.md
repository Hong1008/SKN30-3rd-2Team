# v1 · Track B (실계약) — M:N 커버리지 평가

> 자동 생성: `eval.run_eval.evaluate_coverage_b` · 2026-07-10 14:31:21 · `APP_ENV=prod` · 문서 8건 × 유형 3종
> ⚠️ 라벨 없는 자동 지표 — **절대값은 정답이 아니라 vN(=시스템 버전) 비교 신호**다. 유형 간 조항 겹침으로 커버리지가 비슷할 수 있으니 델타(vN 간)로 해석하고 최적화 목표로 삼지 말 것.
> `coverage = (전체 표준 − MISSING) / 전체 표준`. best-fit = 커버리지 최대 유형.

## 커버리지 매트릭스 (문서 × 유형 — 셀: `coverage (NM=NO_MATCH)`)

| 문서 | 조항수 | SW_FREELANCE | SI_SUBCONTRACT | SM_SUBCONTRACT | best-fit |
| --- | --- | --- | --- | --- | --- |
| raw/01_SW프리랜서용역계약서_기본형.pdf | 12 | 0.30 (NM=0) | 0.09 (NM=0) | 0.08 (NM=0) | SW_FREELANCE |
| raw/02_SW프리랜서용역계약서_EXTRA_NOMATCH강조형.pdf | 17 | 0.22 (NM=0) | 0.12 (NM=0) | 0.11 (NM=0) | SW_FREELANCE |
| raw/03_SW프리랜서용역계약서_CHANGED_EXTRA혼합형.pdf | 15 | 0.13 (NM=0) | 0.11 (NM=0) | 0.08 (NM=0) | SW_FREELANCE |
| raw/test_sunny10.pdf | 14 | 0.39 (NM=0) | 0.12 (NM=0) | 0.13 (NM=0) | SW_FREELANCE |
| raw/동행용역계약서_김효선.pdf | 15 | 0.22 (NM=0) | 0.12 (NM=0) | 0.11 (NM=0) | SW_FREELANCE |
| raw/프리랜서_고용계약서_샘플_문서킹.docx | 12 | 0.13 (NM=0) | 0.05 (NM=0) | 0.05 (NM=0) | SW_FREELANCE |
| raw/프리랜서_고용계약서_샘플_자비스.docx | 10 | 0.00 (NM=0) | 0.00 (NM=0) | 0.00 (NM=0) | SW_FREELANCE |
| raw/프리랜서_고용계약서_샘플_프리폼.docx | 14 | 0.22 (NM=0) | 0.07 (NM=0) | 0.06 (NM=0) | SW_FREELANCE |

## 문서별 상세 (best-fit 유형 기준 deviation 분포)

- **raw/01_SW프리랜서용역계약서_기본형.pdf** (best-fit `SW_FREELANCE`): 조항 12 · coverage 0.30 (표준 7/23) · NO_MATCH 0 · 분포 {'NONE': 7, 'EXTRA': 5}
- **raw/02_SW프리랜서용역계약서_EXTRA_NOMATCH강조형.pdf** (best-fit `SW_FREELANCE`): 조항 17 · coverage 0.22 (표준 5/23) · NO_MATCH 0 · 분포 {'NONE': 5, 'EXTRA': 12}
- **raw/03_SW프리랜서용역계약서_CHANGED_EXTRA혼합형.pdf** (best-fit `SW_FREELANCE`): 조항 15 · coverage 0.13 (표준 3/23) · NO_MATCH 0 · 분포 {'NONE': 3, 'EXTRA': 12}
- **raw/test_sunny10.pdf** (best-fit `SW_FREELANCE`): 조항 14 · coverage 0.39 (표준 9/23) · NO_MATCH 0 · 분포 {'EXTRA': 4, 'NONE': 10}
- **raw/동행용역계약서_김효선.pdf** (best-fit `SW_FREELANCE`): 조항 15 · coverage 0.22 (표준 5/23) · NO_MATCH 0 · 분포 {'NONE': 8, 'EXTRA': 7}
- **raw/프리랜서_고용계약서_샘플_문서킹.docx** (best-fit `SW_FREELANCE`): 조항 12 · coverage 0.13 (표준 3/23) · NO_MATCH 0 · 분포 {'EXTRA': 8, 'NONE': 4}
- **raw/프리랜서_고용계약서_샘플_자비스.docx** (best-fit `SW_FREELANCE`): 조항 10 · coverage 0.00 (표준 0/23) · NO_MATCH 0 · 분포 {'EXTRA': 10} · ⚠️ 축퇴 의심: 전 조항(10건)이 단일 분류(EXTRA) — 분류기가 신호를 못 내고 있을 수 있음
- **raw/프리랜서_고용계약서_샘플_프리폼.docx** (best-fit `SW_FREELANCE`): 조항 14 · coverage 0.22 (표준 5/23) · NO_MATCH 0 · 분포 {'EXTRA': 9, 'NONE': 5}

## 강건성 스팟체크 (사람 작성 — 정성, 지표 없음)

> `run_eval b` 실행 시 함께 출력되는 문서 덤프를 훑고 아래를 채운다.

- 파싱 성공/실패 · 깨진 조항 여부 — 
- best-fit 이 상식과 맞는가(프리랜서 문서가 SW_FREELANCE 로?) · 유형 간 분리가 뚜렷한가 — 
- NO_MATCH 폭주·비정상 deviation 분포 여부 — 
- 기타 — 
