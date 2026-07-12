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

_V5_SPLITS = {"TUNING", "HELD_OUT"}
_V5_ROLES = {
    "검토 강화 EXTRA": Deviation.EXTRA.value,
    "일반 EXTRA": Deviation.EXTRA.value,
    "표준 대응 NONE": Deviation.NONE.value,
}
_V5_EXPECTED_COUNTS = {
    "TUNING": {"total": 30, "EXTRA": 20, "NONE": 10, **{
        "검토 강화 EXTRA": 10, "일반 EXTRA": 10, "표준 대응 NONE": 10,
    }},
    "HELD_OUT": {"total": 15, "EXTRA": 10, "NONE": 5, **{
        "검토 강화 EXTRA": 5, "일반 EXTRA": 5, "표준 대응 NONE": 5,
    }},
}


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


def find_global_duplicate_case_ids(
    cases_by_file: list[list[dict[str, Any]]],
) -> dict[str, int]:
    """v5 전체 골든 파일을 합친 전역 case_id 중복을 반환한다."""
    counts = Counter(
        case.get("case_id")
        for cases in cases_by_file
        for case in cases
    )
    return {case_id: count for case_id, count in counts.items() if count > 1}


def _v5_violation(rule: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "detail": detail}


def validate_v5_cases(
    cases: list[dict[str, Any]],
    case_matrix: list[dict[str, Any]],
    heldout_case_ids: list[str],
) -> list[dict[str, str]]:
    """v5 골든 케이스와 matrix의 연결·분포·split 규칙을 검사한다."""
    violations: list[dict[str, str]] = []
    case_ids = [case.get("case_id") for case in cases]
    matrix_ids = [row.get("case_id") for row in case_matrix]
    case_id_set = set(case_ids)
    matrix_id_set = set(matrix_ids)

    for case_id in sorted(case_id_set - matrix_id_set, key=str):
        violations.append(_v5_violation(
            "case_matrix_missing_case",
            f"matrix에 없는 골든 case_id: {case_id!r}",
        ))
    for case_id in sorted(matrix_id_set - case_id_set, key=str):
        violations.append(_v5_violation(
            "case_matrix_unknown_case",
            f"골든에 없는 matrix case_id: {case_id!r}",
        ))

    for case_id, count in sorted(find_duplicate_case_ids(case_matrix).items(), key=lambda item: str(item[0])):
        violations.append(_v5_violation(
            "case_matrix_duplicate_case_id",
            f"matrix case_id {case_id!r}이(가) {count}회 등장",
        ))

    cases_by_id = {case.get("case_id"): case for case in cases}
    matrix_by_id = {row.get("case_id"): row for row in case_matrix}
    linked_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for case_id in sorted(case_id_set & matrix_id_set, key=str):
        case = cases_by_id[case_id]
        row = matrix_by_id[case_id]
        if row.get("contract_type") != case.get("contract_type"):
            violations.append(_v5_violation(
                "case_matrix_contract_type_mismatch",
                f"case_id {case_id!r}의 contract_type이 골든과 matrix에서 다름",
            ))
        split = row.get("split")
        if not isinstance(split, str) or split not in _V5_SPLITS:
            violations.append(_v5_violation(
                "case_matrix_split_invalid",
                f"case_id {case_id!r}의 split이 TUNING/HELD_OUT이 아님: {split!r}",
            ))
        role = row.get("design_role")
        if not isinstance(role, str) or role not in _V5_ROLES:
            violations.append(_v5_violation(
                "case_matrix_design_role_invalid",
                f"case_id {case_id!r}의 design_role이 허용값이 아님: {role!r}",
            ))
        topic_group = row.get("topic_group")
        if not isinstance(topic_group, str) or not topic_group.strip():
            violations.append(_v5_violation(
                "case_matrix_topic_group_invalid",
                f"case_id {case_id!r}의 topic_group은 비어 있지 않은 문자열이어야 함",
            ))
        if isinstance(split, str) and split in _V5_SPLITS and isinstance(role, str) and role in _V5_ROLES:
            linked_rows.append((case, row))
            if case.get("gold_deviation") != _V5_ROLES[role]:
                violations.append(_v5_violation(
                    "case_matrix_design_role_mismatch",
                    f"case_id {case_id!r}의 design_role과 gold_deviation이 대응하지 않음",
                ))

    groups: dict[tuple[Any, Any], set[str]] = {}
    for _, row in linked_rows:
        key = (row.get("contract_type"), row.get("topic_group"))
        groups.setdefault(key, set()).add(row["split"])
    for key, splits in groups.items():
        if len(splits) > 1:
            violations.append(_v5_violation(
                "topic_group_split_leakage",
                f"{key!r} topic_group이 split을 가로지름: {sorted(splits)}",
            ))

    by_split: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {
        split: [] for split in _V5_SPLITS
    }
    for pair in linked_rows:
        by_split[pair[1]["split"]].append(pair)
    for split, rows in by_split.items():
        expected = _V5_EXPECTED_COUNTS[split]
        deviation_counts = Counter(case.get("gold_deviation") for case, _ in rows)
        role_counts = Counter(row.get("design_role") for _, row in rows)
        if len(rows) != expected["total"] or any(
            deviation_counts.get(deviation, 0) != expected[deviation]
            for deviation in (Deviation.EXTRA.value, Deviation.NONE.value)
        ):
            violations.append(_v5_violation(
                "v5_deviation_distribution",
                f"{split} 분포가 기대값과 다름: cases={len(rows)}, deviations={dict(deviation_counts)}",
            ))
        if any(role_counts.get(role, 0) != expected[role] for role in _V5_ROLES):
            violations.append(_v5_violation(
                "case_matrix_design_role_count",
                f"{split} 역할 분포가 기대값과 다름: {dict(role_counts)}",
            ))
        if not {Deviation.EXTRA.value, Deviation.NONE.value} <= set(deviation_counts):
            violations.append(_v5_violation(
                "single_class_deviation",
                f"{split}에 EXTRA와 NONE 양쪽 클래스가 모두 존재하지 않음",
            ))

    manifest_ids = set(heldout_case_ids)
    matrix_heldout_ids = {
        case.get("case_id") for case, row in linked_rows if row.get("split") == "HELD_OUT"
    }
    if matrix_heldout_ids != (manifest_ids & case_id_set):
        violations.append(_v5_violation(
            "heldout_matrix_mismatch",
            "matrix의 HELD_OUT 선언과 manifest의 해당 파일 case_id가 일치하지 않음",
        ))
    return violations


def validate_v5_manifest(
    cases_by_type: dict[str, list[dict[str, Any]]],
    matrices_by_type: dict[str, list[dict[str, Any]]],
    heldout_case_ids: list[str],
) -> list[dict[str, str]]:
    """v5 전체 파일 범위의 manifest·전역 ID 규칙을 검사한다."""
    violations: list[dict[str, str]] = []
    all_cases = [case for cases in cases_by_type.values() for case in cases]
    all_case_ids = [case.get("case_id") for case in all_cases]
    all_case_id_set = set(all_case_ids)
    for case_id, count in sorted(
        find_global_duplicate_case_ids(list(cases_by_type.values())).items(),
        key=lambda item: str(item[0]),
    ):
        violations.append(_v5_violation(
            "case_id_global_duplicate",
            f"v5 전체 case_id {case_id!r}이(가) {count}회 등장",
        ))
    manifest_counts = Counter(heldout_case_ids)
    for case_id, count in sorted(manifest_counts.items(), key=lambda item: str(item[0])):
        if count > 1:
            violations.append(_v5_violation(
                "heldout_manifest_duplicate_case_id",
                f"held-out manifest case_id {case_id!r}이(가) {count}회 등장",
            ))
    for case_id in sorted(set(heldout_case_ids) - all_case_id_set, key=str):
        violations.append(_v5_violation(
            "heldout_manifest_unknown_case_id",
            f"manifest에만 존재하는 case_id: {case_id!r}",
        ))

    matrix_heldout_ids = {
        row.get("case_id")
        for matrix in matrices_by_type.values()
        for row in matrix
        if row.get("split") == "HELD_OUT"
    }
    if matrix_heldout_ids != (set(heldout_case_ids) & all_case_id_set):
        violations.append(_v5_violation(
            "heldout_matrix_mismatch",
            "v5 전체 matrix의 HELD_OUT 선언과 manifest가 일치하지 않음",
        ))
    return violations


def load_golden_files(version: str, golden_dir: Path = _GOLDEN_DIR) -> list[tuple[Path, list[dict]]]:
    """골든 입력 JSON만 로드한다. 진단·matrix sidecar는 평가 입력이 아니므로 제외한다."""
    files: list[tuple[Path, list[dict]]] = []
    for path in sorted(golden_dir.glob(f"{version}_*.json")):
        # 진단과 v5 case matrix는 골든 케이스 목록이 아닌 sidecar다.
        if path.name.endswith(("_diagnostics.json", "_case_matrix.json")):
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

    def record(path_label: str, violation: dict[str, str]) -> None:
        nonlocal total_violations
        print(f"[{path_label}] {violation['rule']}: {violation['detail']}")
        rule_counts[violation["rule"]] += 1
        total_violations += 1

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

    if version == "v5":
        cases_by_type: dict[str, list[dict[str, Any]]] = {}
        matrices_by_type: dict[str, list[dict[str, Any]]] = {}
        manifest_path = _GOLDEN_DIR / "threshold_heldout.v5.json"
        manifest_ids: list[str] = []

        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_ids = manifest_payload["heldout_case_ids"]
            if not isinstance(manifest_ids, list) or not all(
                isinstance(case_id, str) for case_id in manifest_ids
            ):
                raise ValueError("heldout_case_ids는 문자열 list여야 합니다")
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            record(manifest_path.name, _v5_violation(
                "heldout_manifest_load_error", f"v5 held-out manifest를 읽을 수 없음: {exc}"
            ))

        for path, cases in files:
            contract_type = cases[0].get("contract_type") if cases else path.stem
            cases_by_type[contract_type] = cases
            matrix_stem = path.stem.replace("_subcontract", "").replace("_freelance", "")
            matrix_path = _GOLDEN_DIR / f"{matrix_stem}_case_matrix.json"
            if not matrix_path.exists():
                record(matrix_path.name, _v5_violation(
                    "case_matrix_load_error", "v5 case matrix 파일이 없습니다"
                ))
                matrices_by_type[contract_type] = []
                continue
            try:
                matrix_payload = json.loads(
                    matrix_path.read_text(encoding="utf-8")
                )
                if not isinstance(matrix_payload, list):
                    record(matrix_path.name, _v5_violation(
                        "case_matrix_type_invalid",
                        f"case matrix 최상위 값은 list여야 하는데 {type(matrix_payload).__name__} 타입",
                    ))
                    matrices_by_type[contract_type] = []
                else:
                    matrices_by_type[contract_type] = matrix_payload
            except (OSError, json.JSONDecodeError) as exc:
                record(matrix_path.name, _v5_violation(
                    "case_matrix_load_error", f"v5 case matrix를 읽을 수 없음: {exc}"
                ))
                matrices_by_type[contract_type] = []

        for contract_type, cases in cases_by_type.items():
            matrix = matrices_by_type.get(contract_type, [])
            for violation in validate_v5_cases(cases, matrix, manifest_ids):
                record(f"v5:{contract_type}", violation)
        for violation in validate_v5_manifest(cases_by_type, matrices_by_type, manifest_ids):
            record("v5:manifest", violation)

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
