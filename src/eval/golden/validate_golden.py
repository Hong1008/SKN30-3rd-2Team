"""
[담당: 팀원 D] 골든셋 JSON 스키마 정합성 검사기

배경: v1에서 고쳤던 라벨 enum 불일치 오류가 v2에서 재발했다(사람이 손으로 라벨링하는
JSON은 같은 실수를 반복하기 쉽다). 매 버전 눈으로 확인하는 대신 기계적으로 잡아내
재발을 막는 게 목적이다. 이 스크립트는 골든셋을 "고치지" 않고 "검출"만 한다.

검사 항목 (docs/tasks/D_eval.md §골든셋 스키마 기준):
  1. gold_toxic 은 항상 list 타입
  2. gold_toxic 의 모든 원소가 contracts.enums.ToxicPattern 값
  3. gold_deviation 이 {NONE, EXTRA} 중 하나 (트랙 A 엔 MISSING 없음)
  4. gold_clause_id 가 null 이거나 표준조항 코퍼스(data/03_normalized)에 실재
  5. 같은 파일 내 case_id 중복 금지 (case_id는 계약유형별 파일 스코프 —
     si_subcontract·sw_freelance 파일이 서로 g01 등 같은 id를 재사용하는 것은 정상이라
     파일 간이 아니라 파일 내부에서만 검사한다)

사용법:
    uv run python src/eval/golden/validate_golden.py [version]
    (version 생략 시 golden/ 안에서 가장 높은 vN 자동 탐지)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from config import BASE_DIR  # 프로젝트 루트 단일 진실원 (config.py 재사용)
from contracts.enums import Deviation, ToxicPattern

_GOLDEN_DIR = Path(__file__).resolve().parent  # .../src/eval/golden

# 트랙 A 골든셋엔 MISSING 이 없다 (D_eval.md §골든셋 스키마) — 이 3종만 허용
_TRACK_A_DEVIATIONS = {Deviation.NONE.value, Deviation.EXTRA.value}
_TOXIC_VALUES = {t.value for t in ToxicPattern}

_STANDARD_CLAUSES_GLOB = "data/03_normalized/standard_clauses.*.json"


def load_clause_id_corpus(base_dir: Path = BASE_DIR) -> set[str]:
    """표준조항 코퍼스(data/03_normalized/standard_clauses.*.json) 전체의 clause_id 집합을 모은다."""
    ids: set[str] = set()
    for path in sorted(base_dir.glob(_STANDARD_CLAUSES_GLOB)):
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                cid = item.get("clause_id")
                if cid:
                    ids.add(cid)
    return ids


def validate_case(case: dict[str, Any], clause_id_corpus: set[str] | None) -> list[dict[str, str]]:
    """케이스 1건을 검사해 위반 목록을 반환한다. 위반 없으면 빈 리스트.

    clause_id_corpus 가 None 이면 검사 4(코퍼스 존재)는 건너뛴다(코퍼스 미로딩 상황 대비).
    각 위반 항목: {"rule": 규칙명, "detail": 사람이 읽을 설명}
    """
    violations: list[dict[str, str]] = []

    # 1) gold_toxic 타입 검사 — 반드시 먼저 검사하고, 타입이 틀리면 아래 enum 순회는 건너뛴다.
    #    (문자열을 그대로 순회하면 문자 단위로 쪼개져 잘못된 "위반"이 나는 버그를 피하기 위함)
    gold_toxic = case.get("gold_toxic")
    if gold_toxic is not None and not isinstance(gold_toxic, list):
        violations.append({
            "rule": "gold_toxic_type",
            "detail": f"gold_toxic은 list여야 하는데 {type(gold_toxic).__name__} 타입: {gold_toxic!r}",
        })
        gold_toxic_items: list[Any] = []
    else:
        gold_toxic_items = gold_toxic or []

    # 2) gold_toxic enum 검사
    for t in gold_toxic_items:
        if t not in _TOXIC_VALUES:
            violations.append({
                "rule": "gold_toxic_enum",
                "detail": f"ToxicPattern에 없는 값: {t!r}",
            })

    # 3) gold_deviation enum 검사 (트랙 A: NONE/CHANGED/EXTRA 만 허용)
    deviation = case.get("gold_deviation")
    if deviation not in _TRACK_A_DEVIATIONS:
        violations.append({
            "rule": "gold_deviation_enum",
            "detail": f"gold_deviation은 {{NONE, CHANGED, EXTRA}} 중 하나여야 하는데: {deviation!r}",
        })

    # 4) gold_clause_id 코퍼스 존재 검사 (null 은 EXTRA 케이스로 허용)
    clause_id = case.get("gold_clause_id")
    if clause_id_corpus is not None and clause_id is not None and clause_id not in clause_id_corpus:
        violations.append({
            "rule": "gold_clause_id_missing",
            "detail": f"표준조항 코퍼스에 없는 gold_clause_id: {clause_id!r}",
        })



    return violations


def find_duplicate_case_ids(cases: list[dict[str, Any]]) -> dict[str, int]:
    """case_id 별 등장 횟수를 세어 2회 이상 중복된 것만 반환한다.

    호출 스코프는 파일 1개분의 케이스 목록이어야 한다 — case_id는 계약유형별 파일
    내부에서만 유일하면 되고(si_subcontract·sw_freelance 가 둘 다 g01을 쓰는 것은
    설계상 정상), 버전 전체를 합쳐 비교하면 오탐이 난다.
    """
    counts = Counter(c.get("case_id") for c in cases)
    return {cid: n for cid, n in counts.items() if n > 1}


def load_golden_files(version: str, golden_dir: Path = _GOLDEN_DIR) -> list[tuple[Path, list[dict]]]:
    """골든 입력 JSON만 로드한다. sidecar matrix는 평가 입력이 아니므로 제외한다."""
    files: list[tuple[Path, list[dict]]] = []
    for path in sorted(golden_dir.glob(f"{version}_*.json")):
        # v5의 진단 sidecar는 골든 평가 입력이 아니므로 스키마 검사 대상에서 제외한다.
        if path.name.endswith("_case_matrix.json"):
            continue
        with open(path, encoding="utf-8") as f:
            files.append((path, json.load(f)))
    return files


def detect_latest_version(golden_dir: Path = _GOLDEN_DIR) -> str:
    """golden_dir 의 `v<N>_*.json` 을 스캔해 가장 높은 v<N> 을 반환한다 (없으면 'v1')."""
    versions: set[int] = set()
    for path in golden_dir.glob("v*_*.json"):
        m = re.match(r"v(\d+)_", path.name)
        if m:
            versions.add(int(m.group(1)))
    return f"v{max(versions)}" if versions else "v1"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    version = argv[0] if argv else detect_latest_version()

    files = load_golden_files(version)
    if not files:
        print(f"[validate_golden] '{version}_*.json' 에 해당하는 골든셋 파일을 찾지 못했습니다.")
        return 1

    clause_id_corpus = load_clause_id_corpus()

    total_violations = 0
    rule_counts: Counter[str] = Counter()
    all_cases: list[dict[str, Any]] = []

    for path, cases in files:
        file_violation_count = 0
        for case in cases:
            case_id = case.get("case_id", "<no case_id>")
            for v in validate_case(case, clause_id_corpus):
                print(f"[{path.name}] case_id={case_id} · {v['rule']}: {v['detail']}")
                rule_counts[v["rule"]] += 1
                total_violations += 1
                file_violation_count += 1

        # 6) case_id 중복 검사 — 파일(계약유형) 스코프 (si·sw 가 서로 g01을 재사용하는 건 정상)
        dups = find_duplicate_case_ids(cases)
        for case_id, count in sorted(dups.items()):
            print(f"[{path.name}] case_id 중복: {case_id!r} 이(가) {count}회 등장")
            rule_counts["case_id_duplicate"] += 1
            total_violations += 1
            file_violation_count += 1

        all_cases.extend(cases)
        if file_violation_count:
            print(f"  └─ {path.name}: {file_violation_count}건 위반")

    print()
    if total_violations == 0:
        print(f"OK — {version} 골든셋({len(all_cases)}건) 스키마 검증 통과, 위반 없음.")
        return 0

    print(f"총 위반 {total_violations}건 (버전={version}, 케이스={len(all_cases)}건)")
    for rule, count in rule_counts.most_common():
        print(f"  - {rule}: {count}건")
    return 1


if __name__ == "__main__":
    sys.exit(main())
