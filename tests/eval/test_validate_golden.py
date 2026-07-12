"""
[담당: 팀원 D] eval.golden.validate_golden — 골든셋 스키마 검증 순수 함수 테스트

파일 I/O(load_golden_files·load_clause_id_corpus)는 제외하고, 케이스 1건 단위 검증
로직(validate_case)과 중복 탐지(find_duplicate_case_ids)만 테스트한다.
"""

import json


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


def test_load_golden_files는_진단과_case_matrix_sidecar를_제외한다(tmp_path):
    """검증 CLI가 v5 sidecar를 골든 케이스로 해석하지 않는다."""
    from eval.golden.validate_golden import load_golden_files

    (tmp_path / "v5_sw_freelance.json").write_text(
        json.dumps([_case(case_id="v5-case")]), encoding="utf-8"
    )
    (tmp_path / "v5_diagnostics.json").write_text(
        json.dumps({"deviation": []}), encoding="utf-8"
    )
    (tmp_path / "v5_sw_case_matrix.json").write_text(
        json.dumps([{"case_id": "v5-case"}]), encoding="utf-8"
    )

    files = load_golden_files("v5", tmp_path)

    assert [path.name for path, _ in files] == ["v5_sw_freelance.json"]


def _v5_fixture(
    prefix: str = "sw",
    contract_type: str = "SW_FREELANCE",
) -> tuple[list[dict], list[dict]]:
    """정확한 v5 한 계약유형 fixture를 생성한다."""
    cases = []
    matrix = []
    case_number = 1
    for split, group_count in (("TUNING", 10), ("HELD_OUT", 5)):
        for group_number in range(1, group_count + 1):
            topic_group = f"{prefix}-{split.lower()}-{group_number:02d}"
            for role, deviation in (
                ("검토 강화 EXTRA", "EXTRA"),
                ("일반 EXTRA", "EXTRA"),
                ("표준 대응 NONE", "NONE"),
            ):
                case_id = f"v5-{prefix}-{case_number:02d}"
                cases.append({
                    "case_id": case_id,
                    "contract_type": contract_type,
                    "gold_deviation": deviation,
                })
                matrix.append({
                    "case_id": case_id,
                    "contract_type": contract_type,
                    "topic_group": topic_group,
                    "split": split,
                    "design_role": role,
                })
                case_number += 1
    return cases, matrix


def _rules(violations):
    return {violation["rule"] for violation in violations}


def test_v5_정상_fixture는_정확한_분포를_통과한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    heldout = [case["case_id"] for case, row in zip(cases, matrix) if row["split"] == "HELD_OUT"]
    assert validate_v5_cases(cases, matrix, heldout) == []


def test_v5_matrix와_case_ID_집합이_다르면_위반한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    matrix[-1]["case_id"] = "ghost"
    violations = validate_v5_cases(cases, matrix, [])
    assert {"case_matrix_missing_case", "case_matrix_unknown_case"} <= _rules(violations)


def test_v5_matrix_split_타입과_enum을_검증한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    matrix[0]["split"] = 1
    matrix[1]["split"] = "UNKNOWN"
    rules = _rules(validate_v5_cases(cases, matrix, []))
    assert "case_matrix_split_invalid" in rules


def test_v5_역할별_정확한_분포를_검증한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    matrix[0]["design_role"] = "일반 EXTRA"
    rules = _rules(validate_v5_cases(cases, matrix, []))
    assert "case_matrix_design_role_count" in rules


def test_v5_design_role과_gold_deviation_대응을_검증한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    matrix[0]["design_role"] = "알 수 없는 역할"
    matrix[1]["topic_group"] = ""
    rules = _rules(validate_v5_cases(cases, matrix, []))
    assert "case_matrix_design_role_invalid" in rules
    assert "case_matrix_topic_group_invalid" in rules


def test_v5_topic_group은_계약유형별로_split_누출을_검증한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    matrix[30]["topic_group"] = matrix[0]["topic_group"]
    rules = _rules(validate_v5_cases(cases, matrix, []))
    assert "topic_group_split_leakage" in rules


def test_v5_전역_case_ID_중복을_탐지한다():
    from eval.golden.validate_golden import find_global_duplicate_case_ids

    assert find_global_duplicate_case_ids([
        [{"case_id": "same"}],
        [{"case_id": "same"}, {"case_id": "other"}],
    ]) == {"same": 2}


def test_v5_다른_계약유형의_동일_topic_group은_누출이_아니다():
    from eval.golden.validate_golden import validate_v5_cases

    _, si_matrix = _v5_fixture("si", "SI_SUBCONTRACT")
    si_cases, _ = _v5_fixture("si", "SI_SUBCONTRACT")
    _, sm_matrix = _v5_fixture("sm", "SM_SUBCONTRACT")
    sm_cases, _ = _v5_fixture("sm", "SM_SUBCONTRACT")
    sm_matrix[0]["topic_group"] = si_matrix[0]["topic_group"]
    assert "topic_group_split_leakage" not in _rules(
        validate_v5_cases(si_cases, si_matrix, [])
    )
    assert "topic_group_split_leakage" not in _rules(
        validate_v5_cases(sm_cases, sm_matrix, [])
    )


def test_v5_유효한_role이라도_gold_deviation이_반대면_위반한다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    cases[0]["gold_deviation"] = "NONE"
    assert "case_matrix_design_role_mismatch" in _rules(
        validate_v5_cases(cases, matrix, [])
    )


def test_v5_manifest_중복과_전역_unknown을_분리한다():
    from eval.golden.validate_golden import validate_v5_manifest

    cases, matrix = _v5_fixture()
    violations = validate_v5_manifest(
        {"SW_FREELANCE": cases},
        {"SW_FREELANCE": matrix},
        [cases[-1]["case_id"], cases[-1]["case_id"], "ghost"],
    )
    assert "heldout_manifest_duplicate_case_id" in _rules(violations)
    assert "heldout_manifest_unknown_case_id" in _rules(violations)


def test_v5_manifest와_matrix의_heldout_선언은_양방향으로_일치해야_한다():
    from eval.golden.validate_golden import validate_v5_manifest

    cases, matrix = _v5_fixture()
    heldout = [case["case_id"] for case, row in zip(cases, matrix) if row["split"] == "HELD_OUT"]
    heldout.remove(cases[-1]["case_id"])
    rules = _rules(validate_v5_manifest(
        {"SW_FREELANCE": cases}, {"SW_FREELANCE": matrix}, heldout
    ))
    assert "heldout_matrix_mismatch" in rules


def test_v5_manifest에_있지만_matrix가_TUNING이면_역방향_위반이다():
    from eval.golden.validate_golden import validate_v5_manifest

    cases, matrix = _v5_fixture()
    tuning_id = cases[0]["case_id"]
    rules = _rules(validate_v5_manifest(
        {"SW_FREELANCE": cases}, {"SW_FREELANCE": matrix}, [tuning_id]
    ))
    assert "heldout_matrix_mismatch" in rules


def test_v5_manifest_세_계약유형_정상_fixture는_통과한다():
    from eval.golden.validate_golden import validate_v5_cases, validate_v5_manifest

    cases_by_type = {}
    matrices_by_type = {}
    heldout = []
    for prefix, contract_type in (
        ("si", "SI_SUBCONTRACT"),
        ("sm", "SM_SUBCONTRACT"),
        ("sw", "SW_FREELANCE"),
    ):
        cases, matrix = _v5_fixture(prefix, contract_type)
        cases_by_type[contract_type] = cases
        matrices_by_type[contract_type] = matrix
        heldout.extend(
            case["case_id"] for case, row in zip(cases, matrix)
            if row["split"] == "HELD_OUT"
        )
        assert validate_v5_cases(cases, matrix, heldout) == []
    assert validate_v5_manifest(cases_by_type, matrices_by_type, heldout) == []


def test_v5_단일_클래스_split은_비교_대상으로_허용하지_않는다():
    from eval.golden.validate_golden import validate_v5_cases

    cases, matrix = _v5_fixture()
    for case, row in zip(cases, matrix):
        if row["split"] == "HELD_OUT":
            case["gold_deviation"] = "EXTRA"
    rules = _rules(validate_v5_cases(cases, matrix, []))
    assert "single_class_deviation" in rules


def test_cli_v4는_v5_sidecar_없이_기존_흐름을_유지한다(tmp_path, monkeypatch, capsys):
    import eval.golden.validate_golden as validator

    (tmp_path / "v4_sw_freelance.json").write_text(
        json.dumps([_case(case_id="v4-1")]), encoding="utf-8"
    )
    monkeypatch.setattr(validator, "_GOLDEN_DIR", tmp_path)
    monkeypatch.setattr(
        validator,
        "load_golden_files",
        lambda version: [(tmp_path / "v4_sw_freelance.json", [_case(case_id="v4-1")])],
    )
    monkeypatch.setattr(validator, "load_clause_id_corpus", lambda: set())

    assert validator.main(["v4"]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_v5는_matrix_manifest_누락을_규칙과_종료코드로_보고한다(tmp_path, monkeypatch, capsys):
    import eval.golden.validate_golden as validator

    for stem, contract_type in (
        ("si_subcontract", "SI_SUBCONTRACT"),
        ("sm_subcontract", "SM_SUBCONTRACT"),
        ("sw_freelance", "SW_FREELANCE"),
    ):
        (tmp_path / f"v5_{stem}.json").write_text(
            json.dumps([_case(case_id=f"{stem}-1", contract_type=contract_type)]),
            encoding="utf-8",
        )
    (tmp_path / "v5_si_case_matrix.json").write_text(json.dumps({"bad": True}), encoding="utf-8")
    monkeypatch.setattr(validator, "_GOLDEN_DIR", tmp_path)
    monkeypatch.setattr(
        validator,
        "load_golden_files",
        lambda version: [
            (path, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(tmp_path.glob("v5_*.json"))
            if not path.name.endswith("_case_matrix.json")
        ],
    )
    monkeypatch.setattr(validator, "load_clause_id_corpus", lambda: set())

    assert validator.main(["v5"]) == 1
    output = capsys.readouterr().out
    assert "heldout_manifest_load_error" in output
    assert "case_matrix_type_invalid" in output
    assert "case_matrix_load_error" in output
