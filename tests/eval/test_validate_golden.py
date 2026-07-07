"""
[담당: 팀원 D] eval.golden.validate_golden — 골든셋 스키마 검증 순수 함수 테스트

파일 I/O(load_golden_files·load_clause_id_corpus)는 제외하고, 케이스 1건 단위 검증
로직(validate_case)과 중복 탐지(find_duplicate_case_ids)만 테스트한다.
"""


def _case(**overrides):
    base = {
        "case_id": "c1",
        "gold_deviation": "NONE",
        "gold_clause_id": None,
        "gold_toxic": None,
        "trap": "none",
    }
    base.update(overrides)
    return base


def test_gold_toxic_문자열이면_타입_위반():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(_case(gold_toxic="UNFAIR_DAMAGE_CLAIM"), clause_id_corpus=None)
    rules = [v["rule"] for v in violations]
    assert "gold_toxic_type" in rules


def test_gold_toxic_문자열_순회로_인한_문자단위_오탐_방지():
    """타입 위반 시 문자열을 순회해 문자 단위로 enum 위반을 만들면 안 된다."""
    from eval.golden.validate_golden import validate_case
    violations = validate_case(_case(gold_toxic="AB"), clause_id_corpus=None)
    enum_violations = [v for v in violations if v["rule"] == "gold_toxic_enum"]
    assert enum_violations == []


def test_gold_toxic_리스트에_잘못된_enum값():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(_case(gold_toxic=["liability_transfer"]), clause_id_corpus=None)
    rules = [v["rule"] for v in violations]
    assert "gold_toxic_enum" in rules
    assert "gold_toxic_type" not in rules


def test_gold_toxic_정상_리스트는_위반_없음():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(_case(gold_toxic=["IP_TOTAL_FREE"]), clause_id_corpus=None)
    assert violations == []


def test_gold_toxic_없으면_통과():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(_case(gold_toxic=None), clause_id_corpus=None)
    assert violations == []


def test_gold_deviation_MISSING은_트랙A에서_위반():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(_case(gold_deviation="MISSING"), clause_id_corpus=None)
    rules = [v["rule"] for v in violations]
    assert "gold_deviation_enum" in rules


def test_gold_deviation_NONE_EXTRA는_통과():
    from eval.golden.validate_golden import validate_case
    for d in ("NONE", "EXTRA"):
        assert validate_case(_case(gold_deviation=d), clause_id_corpus=None) == []


def test_gold_clause_id_코퍼스에_없으면_위반():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(
        _case(gold_clause_id="not_in_corpus"), clause_id_corpus={"sm_subcontract-2025-art1"}
    )
    rules = [v["rule"] for v in violations]
    assert "gold_clause_id_missing" in rules


def test_gold_clause_id_null은_EXTRA로_허용():
    from eval.golden.validate_golden import validate_case
    violations = validate_case(
        _case(gold_clause_id=None, gold_deviation="EXTRA"), clause_id_corpus={"a"}
    )
    assert violations == []





def test_find_duplicate_case_ids_중복_탐지():
    from eval.golden.validate_golden import find_duplicate_case_ids
    cases = [_case(case_id="g01"), _case(case_id="g01"), _case(case_id="g02")]
    dups = find_duplicate_case_ids(cases)
    assert dups == {"g01": 2}


def test_find_duplicate_case_ids_중복없으면_빈딕셔너리():
    from eval.golden.validate_golden import find_duplicate_case_ids
    cases = [_case(case_id="g01"), _case(case_id="g02")]
    assert find_duplicate_case_ids(cases) == {}
