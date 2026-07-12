"""v5 골든셋과 진단 sidecar의 구조·분포·split 격리 검증."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from eval.golden.validate_golden import load_clause_id_corpus


GOLDEN_DIR = Path(__file__).resolve().parents[2] / "src/eval/golden"
TYPES = {
    "si_subcontract": "SI_SUBCONTRACT",
    "sm_subcontract": "SM_SUBCONTRACT",
    "sw_freelance": "SW_FREELANCE",
}
ROLES = {"검토 강화 EXTRA", "일반 EXTRA", "표준 대응 NONE"}
TRAPS = {
    "none",
    "paraphrase",
    "partial",
    "reorder",
    "number",
    "negation",
    "party",
    "contradiction",
}


def _load(name: str) -> list[dict]:
    with open(GOLDEN_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def test_v5_golden_sidecar_구조와_분포():
    corpus = load_clause_id_corpus()
    manifest = _load("threshold_heldout.v5.json")
    heldout_ids = set(manifest["heldout_case_ids"])
    expected_heldout_ids = {
        f"v5-{prefix}-{number:02d}"
        for prefix in ("si", "sm", "sw")
        for number in range(31, 46)
    }
    assert heldout_ids == expected_heldout_ids

    for stem, contract_type in TYPES.items():
        cases = _load(f"v5_{stem}.json")
        if stem == "si_subcontract":
            matrix = _load("v5_si_case_matrix.json")
        elif stem == "sm_subcontract":
            matrix = _load("v5_sm_case_matrix.json")
        else:
            matrix = _load("v5_sw_case_matrix.json")

        assert len(cases) == 45
        assert len(matrix) == 45
        case_by_id = {case["case_id"]: case for case in cases}
        matrix_by_id = {row["case_id"]: row for row in matrix}
        assert len(case_by_id) == 45
        assert len(matrix_by_id) == 45
        assert set(case_by_id) == set(matrix_by_id)

        assert all(case["contract_type"] == contract_type for case in cases)
        assert all(row["contract_type"] == contract_type for row in matrix)
        assert {case["case_id"] for case in cases} & heldout_ids == {
            f"v5-{stem.split('_')[0]}-{n:02d}" for n in range(31, 46)
        }

        for case in cases:
            assert case["gold_toxic"] is not None
            assert isinstance(case["gold_toxic"], list)
            assert case["trap"] in TRAPS
            if case["gold_deviation"] == "EXTRA":
                assert case["gold_clause_id"] is None
            else:
                assert case["gold_deviation"] == "NONE"
                assert case["gold_clause_id"] in corpus

        grouped_rows = defaultdict(list)
        for case, row in zip(cases, matrix):
            assert case["case_id"] == row["case_id"]
            assert row["design_role"] in ROLES
            assert row["split"] in {"TUNING", "HELD_OUT"}
            assert row["topic_group"]
            grouped_rows[row["topic_group"]].append((case, row))

        assert len(grouped_rows) == 15
        for topic_group, members in grouped_rows.items():
            assert len(members) == 3, topic_group
            assert [row["design_role"] for _, row in members] == [
                "검토 강화 EXTRA",
                "일반 EXTRA",
                "표준 대응 NONE",
            ]
            assert len({row["split"] for _, row in members}) == 1
            none_case, none_row = members[2]
            assert none_case["gold_deviation"] == "NONE"
            for case, row in members[:2]:
                assert case["gold_deviation"] == "EXTRA"
                assert row["contrast_clause_id"] == none_case["gold_clause_id"]
                assert row["contrast_clause_id"] in corpus
                assert row["contrast_reason"]
            assert none_row["contrast_clause_id"] is None
            assert none_row["contrast_reason"] is None

        by_split = defaultdict(list)
        for case, row in zip(cases, matrix):
            by_split[row["split"]].append(case)
        assert len(by_split["TUNING"]) == 30
        assert len(by_split["HELD_OUT"]) == 15
        for split, split_cases in by_split.items():
            assert Counter(c["gold_deviation"] for c in split_cases) == {
                "EXTRA": 20 if split == "TUNING" else 10,
                "NONE": 10 if split == "TUNING" else 5,
            }
            traps = {c["trap"] for c in split_cases}
            assert {"paraphrase", "partial", "reorder"} <= traps
            assert len(traps & {"number", "negation", "party", "contradiction"}) >= 2

            for topic_group, members in grouped_rows.items():
                if members[0][1]["split"] == split:
                    assert any(case["trap"] != "none" for case, _ in members)
