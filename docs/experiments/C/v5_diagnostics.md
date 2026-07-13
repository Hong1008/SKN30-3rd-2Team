# v5 — case-level 진단

> eval 전용 결정론적 후보·오류 분해 기록입니다. MCP 응답이나 계약 판정에는 사용하지 않습니다.

## 이탈 case-level 진단

| case_id | 유형 | outcome | reason |
| --- | --- | --- | --- |
| v5-sw-31 | SW_FREELANCE | TP | CORRECT |
| v5-sw-32 | SW_FREELANCE | TP | CORRECT |
| v5-sw-33 | SW_FREELANCE | TN | CORRECT |
| v5-sw-34 | SW_FREELANCE | FN | OVER_MATCH |
| v5-sw-35 | SW_FREELANCE | FN | OVER_MATCH |
| v5-sw-36 | SW_FREELANCE | FP | UNDER_MATCH |
| v5-sw-37 | SW_FREELANCE | TP | BELOW_THRESHOLD |
| v5-sw-38 | SW_FREELANCE | TP | BELOW_THRESHOLD |
| v5-sw-39 | SW_FREELANCE | TN | CORRECT |
| v5-sw-40 | SW_FREELANCE | TP | BELOW_THRESHOLD |
| v5-sw-41 | SW_FREELANCE | TP | BELOW_THRESHOLD |
| v5-sw-42 | SW_FREELANCE | FP | UNDER_MATCH |
| v5-sw-43 | SW_FREELANCE | TP | BELOW_THRESHOLD |
| v5-sw-44 | SW_FREELANCE | TP | BELOW_THRESHOLD |
| v5-sw-45 | SW_FREELANCE | TN | CORRECT |

## 독소 case-level 진단

| case_id | 유형 | outcome | reason |
| --- | --- | --- | --- |
| v5-sw-31 | SW_FREELANCE | TP | CORRECT |
| v5-sw-32 | SW_FREELANCE | TN | CORRECT |
| v5-sw-33 | SW_FREELANCE | FP | WRONG_PATTERN |
| v5-sw-34 | SW_FREELANCE | TP | CORRECT |
| v5-sw-35 | SW_FREELANCE | TN | CORRECT |
| v5-sw-36 | SW_FREELANCE | FP | WRONG_PATTERN |
| v5-sw-37 | SW_FREELANCE | TN | CORRECT |
| v5-sw-38 | SW_FREELANCE | TN | CORRECT |
| v5-sw-39 | SW_FREELANCE | TN | CORRECT |
| v5-sw-40 | SW_FREELANCE | TN | CORRECT |
| v5-sw-41 | SW_FREELANCE | TN | CORRECT |
| v5-sw-42 | SW_FREELANCE | TN | CORRECT |
| v5-sw-43 | SW_FREELANCE | TN | CORRECT |
| v5-sw-44 | SW_FREELANCE | TN | CORRECT |
| v5-sw-45 | SW_FREELANCE | FP | WRONG_PATTERN |
