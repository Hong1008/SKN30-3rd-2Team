import json
import re
from pathlib import Path
import pytest

from contracts.enums import Deviation, ToxicPattern

# 경로 설정: tests/eval/test_v4_heldout.py에서 legacy golden 위치
GOLDEN_DIR = Path(__file__).resolve().parents[2] / "quality/fixtures/legacy/golden"

def normalize_text(text: str) -> str:
    """공백과 개행, 특수 기호 등을 제거하여 문구 일치를 정규화한다."""
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', text)

def test_v4_heldout_rules():
    # 1. v4 골든셋 및 heldout 매니페스트 로드
    v4_files = [
        p for p in GOLDEN_DIR.glob("v4_*.json")
        if "si_subcontract" in p.name or "sm_subcontract" in p.name or "sw_freelance" in p.name
    ]
    assert len(v4_files) == 3, f"v4 골든셋 파일은 3개여야 합니다. (찾은 개수: {len(v4_files)})"

    v4_cases = []
    for p in v4_files:
        with open(p, encoding="utf-8") as f:
            v4_cases.extend(json.load(f))

    # v3 골든셋 로드
    v3_files = [
        p for p in GOLDEN_DIR.glob("v3_*.json")
        if "si_subcontract" in p.name or "sm_subcontract" in p.name or "sw_freelance" in p.name
    ]
    v3_cases = []
    for p in v3_files:
        with open(p, encoding="utf-8") as f:
            v3_cases.extend(json.load(f))

    # heldout 매니페스트 로드
    heldout_path = GOLDEN_DIR / "threshold_heldout.v4.json"
    assert heldout_path.exists(), "threshold_heldout.v4.json 파일이 존재해야 합니다."
    with open(heldout_path, encoding="utf-8") as f:
        heldout_manifest = json.load(f)
    heldout_ids = set(heldout_manifest["heldout_case_ids"])

    # 2. 검증 준비
    v4_ids = {c["case_id"] for c in v4_cases}
    v4_by_id = {c["case_id"]: c for c in v4_cases}
    v4_by_type = {}
    for c in v4_cases:
        v4_by_type.setdefault(c["contract_type"], []).append(c)

    # 규칙 1: held-out case ID가 v4 골든에 모두 존재해야 함
    for hid in heldout_ids:
        assert hid in v4_ids, f"Held-out case_id '{hid}'가 v4 골든셋에 존재하지 않습니다."

    # 규칙 2: tuning/held-out 교집합 없음
    tuning_ids = v4_ids - heldout_ids
    assert not (tuning_ids & heldout_ids), "Tuning과 Held-out의 ID 교집합이 발생했습니다."

    # 규칙 3: held-out에 필수 5 pattern 각각 최소 1건 포함
    required_patterns = {
        "UNFAIR_DAMAGE_CLAIM",
        "UNPAID_ADDITIONAL_WORK",
        "UNILATERAL_CHANGE",
        "NONCOMPETE_EXCESS",
        "INDEFINITE_CONFIDENTIALITY"
    }
    heldout_patterns = set()
    for hid in heldout_ids:
        case = v4_by_id[hid]
        for pattern in (case.get("gold_toxic") or []):
            heldout_patterns.add(pattern)
    
    for rp in required_patterns:
        assert rp in heldout_patterns, f"필수 패턴 '{rp}'가 held-out에 포함되지 않았습니다."

    # 규칙 4: 계약유형별 held-out 최소 1개 이상의 독소 양성 포함
    for ctype, cases in v4_by_type.items():
        type_heldout = [c for c in cases if c["case_id"] in heldout_ids]
        toxic_count = sum(1 for c in type_heldout if c.get("gold_toxic"))
        assert toxic_count >= 1, f"계약유형 {ctype}의 held-out에 독소 양성이 없습니다."

    # 규칙 5: 양성/hard-negative 쌍이 split을 가로지르지 않음
    # (홀수/짝수 인접 케이스: v4-si-01/02, v4-si-03/04 등이 모두 동일 split에 있어야 함)
    for ctype, cases in v4_by_type.items():
        sorted_cases = sorted(cases, key=lambda x: x["case_id"])
        for idx in range(0, len(sorted_cases), 2):
            if idx + 1 < len(sorted_cases):
                c1 = sorted_cases[idx]
                c2 = sorted_cases[idx+1]
                s1 = "heldout" if c1["case_id"] in heldout_ids else "tuning"
                s2 = "heldout" if c2["case_id"] in heldout_ids else "tuning"
                assert s1 == s2, f"쌍 {c1['case_id']}({s1})와 {c2['case_id']}({s2})가 다른 split에 배분되어 격리에 위배됩니다."

    # 규칙 6: v3·v4 간 정규화 문구 정확 중복 없음
    v3_normalized_clauses = {normalize_text(c["user_clause"]) for c in v3_cases}
    for c in v4_cases:
        norm_v4 = normalize_text(c["user_clause"])
        assert norm_v4 not in v3_normalized_clauses, f"v4의 '{c['case_id']}' 문구가 v3 문구와 정규화 기준 정확히 중복됩니다."

    # 규칙 7: gold_deviation=EXTRA면 gold_clause_id=null
    for c in v4_cases:
        if c.get("gold_deviation") == "EXTRA":
            assert c.get("gold_clause_id") is None, f"EXTRA 케이스 '{c['case_id']}'는 gold_clause_id가 null이어야 합니다."

    # 규칙 8: Track A에는 MISSING을 넣지 않음
    for c in v4_cases:
        assert c.get("gold_deviation") != "MISSING", f"Track A 골든셋 '{c['case_id']}'에 허용되지 않은 MISSING 이탈이 포함되었습니다."
