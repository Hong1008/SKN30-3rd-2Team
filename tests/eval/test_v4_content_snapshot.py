import hashlib
import json
import unicodedata
from pathlib import Path


GOLDEN_DIR = Path(__file__).resolve().parents[2] / "quality/fixtures/legacy/golden"
SNAPSHOT = Path(__file__).parent / "fixtures/v4_content_snapshot.v4.json"


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return " ".join(value.split())


def _sha256(value: str) -> str:
    return hashlib.sha256(_normalize(value).encode("utf-8")).hexdigest()


def _load_cases():
    cases = []
    for path in sorted(GOLDEN_DIR.glob("v4_*.json")):
        if "diagnostics" in path.name:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cases.extend(data)
    return {case["case_id"]: case for case in cases}


def test_v4_content_snapshot_matches():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    cases = _load_cases()
    assert set(cases) == set(snapshot["cases"])
    assert len(cases) == 54
    for case_id, case in cases.items():
        expected = snapshot["cases"][case_id]
        assert _sha256(case["user_clause"]) == expected["user_clause_sha256"], case_id
        assert _sha256(case.get("note", "")) == expected["note_sha256"], case_id
        assert case["gold_deviation"] == expected["gold_deviation"], case_id
        assert case.get("gold_clause_id") == expected["gold_clause_id"], case_id
        assert case.get("gold_toxic") == expected["gold_toxic"], case_id

    heldout_ids = set(
        json.loads(
            (GOLDEN_DIR / "threshold_heldout.v4.json").read_text(encoding="utf-8")
        )["heldout_case_ids"]
    )
    for case_id, expected in snapshot["cases"].items():
        assert (case_id in heldout_ids) == expected["heldout"], case_id


def test_v4_static_invariants():
    cases = _load_cases()
    heldout = json.loads(
        (GOLDEN_DIR / "threshold_heldout.v4.json").read_text(encoding="utf-8")
    )["heldout_case_ids"]
    assert len(cases) == 54
    assert {case["contract_type"] for case in cases.values()} == {
        "SI_SUBCONTRACT",
        "SM_SUBCONTRACT",
        "SW_FREELANCE",
    }
    for contract_type in ("SI_SUBCONTRACT", "SM_SUBCONTRACT", "SW_FREELANCE"):
        assert sum(case["contract_type"] == contract_type for case in cases.values()) == 18
    assert len(heldout) == 18
    assert {case_id for case_id in heldout} <= set(cases)
    assert all(
        case["contract_type"] == "SM_SUBCONTRACT"
        for case in cases.values()
        if case["gold_deviation"] == "EXTRA"
    )
    assert all(case["gold_deviation"] != "MISSING" for case in cases.values())
