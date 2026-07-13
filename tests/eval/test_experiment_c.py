"""실험 C의 v5 SW 분할·OVER_MATCH 정의·승인 규격 테스트."""
import json

import pytest


def _sw_cases_and_baseline():
    cases = json.loads(open("src/eval/golden/v5_sw_freelance.json", encoding="utf-8").read())
    rows = json.loads(open("src/eval/golden/v5_diagnostics.json", encoding="utf-8").read())["deviation"]
    return cases, [row for row in rows if row["contract_type"] == "SW_FREELANCE"]


def test_v5_sw는_topic_group_누출없이_30_15로_분할된다():
    from eval.experiment_c import split_sw_cases

    cases = json.loads(open("src/eval/golden/v5_sw_freelance.json", encoding="utf-8").read())
    result = split_sw_cases(cases)
    assert len(result["tuning"]) == 30
    assert len(result["held-out"]) == 15
    assert {case["topic_group"] for case in result["tuning"]}.isdisjoint(
        {case["topic_group"] for case in result["held-out"]}
    )


def test_overmatch는_EXTRA가_NONE으로_예측된_행만_포함한다():
    from eval.experiment_c import is_overmatch

    assert is_overmatch({"gold_deviation": "EXTRA", "predicted_deviation": "NONE"})
    assert not is_overmatch({"gold_deviation": "EXTRA", "predicted_deviation": "EXTRA"})
    assert not is_overmatch({"gold_deviation": "NONE", "predicted_deviation": "EXTRA"})


def test_C_후보비교진단은_표준조항과_서브청크부모를_분리한다():
    from eval.experiment_c import build_candidate_comparison

    rows = [{
        "case_id": "v5-sw-01",
        "gold_deviation": "EXTRA",
        "predicted_deviation": "NONE",
        "top_candidates": [
            {"source": "standard_sub_chunks", "parent_clause_id": "art-1", "score": 0.91},
            {"source": "standard_clauses", "standard_id": "art-1", "score": 0.88},
            {"source": "standard_sub_chunks", "parent_clause_id": "art-2", "score": 0.20},
        ],
    }]

    result = build_candidate_comparison(rows)

    assert result == [{
        "case_id": "v5-sw-01",
        "outcome": None,
        "is_overmatch": True,
        "standard_clause_id": "art-1",
        "standard_clause_score": 0.88,
        "sub_chunk_parent_clause_id": "art-1",
        "sub_chunk_score": 0.91,
        "parents_agree": True,
        "winner": "SUB_CHUNK",
        "winner_score_gap": 0.03,
    }]


def test_C_준비진단은_동결된_tuning만_비교표로_쓴다(tmp_path):
    from eval.experiment_c import prepare_candidate_diagnostics

    paths = prepare_candidate_diagnostics(tmp_path)

    overmatch = (tmp_path / "C_candidate_comparison.md").read_text(encoding="utf-8")
    all_tuning = (tmp_path / "C_source_agreement.md").read_text(encoding="utf-8")
    assert paths["overmatch"].endswith("C_candidate_comparison.md")
    assert "v5-sw-01" in overmatch
    assert "v5-sw-31" not in overmatch
    assert "v5-sw-30" in all_tuning
    assert "v5-sw-31" not in all_tuning
    assert "tuning 전체만 사용합니다. held-out은 읽지 않습니다." in all_tuning


def test_c_승인_파일은_실험_ID와_기준선_커밋을_검증한다():
    from eval.experiment_c import EXPERIMENT_C, validate_c_approval

    approval = {
        "experiment_id": "C", "baseline_commit": EXPERIMENT_C.baseline_commit,
        "runtime_tree_sha": "tree", "manifest_sha256": "manifest",
        "tuning_report_sha256": "tuning", "approved_by": "reviewer",
        "approved_at": "2026-07-13T00:00:00+09:00", "allowed_split": "held-out",
    }
    validate_c_approval(approval, manifest_sha256="manifest", tuning_report_sha256="tuning", runtime_tree_sha="tree")
    approval["experiment_id"] = "S"
    with pytest.raises(ValueError, match="experiment_id"):
        validate_c_approval(approval, manifest_sha256="manifest", tuning_report_sha256="tuning", runtime_tree_sha="tree")


def test_c_tuning_실행_경로는_판정하고_결과와_taxonomy를_쓴다(monkeypatch, tmp_path):
    import eval.run_eval as run_eval

    cases, baseline_rows = _sw_cases_and_baseline()
    output_dir = tmp_path / "C"
    monkeypatch.setattr(run_eval, "EXPERIMENT_C_DIR", output_dir)
    monkeypatch.setattr(run_eval, "EXPERIMENT_C_BASELINE", tmp_path / "baseline.json")
    monkeypatch.setattr(run_eval, "validate_baseline_inputs", lambda *_args: {})
    monkeypatch.setattr(run_eval, "_load_golden", lambda _version: cases)

    def fake_track(**_kwargs):
        selected = {case["case_id"] for case in cases[:30]}
        rows = []
        for row in baseline_rows:
            if row["case_id"] not in selected:
                continue
            copy = dict(row)
            if copy["gold_deviation"] == "EXTRA":
                copy["predicted_deviation"] = "EXTRA"
                copy["outcome"] = "TP"
            rows.append(copy)
        return {"diagnostics": {"deviation": rows}}

    monkeypatch.setattr(run_eval, "_run_track_a", fake_track)
    result = run_eval._run_experiment_c("tuning")
    assert result["passed"] is True
    assert (output_dir / "tuning-result.json").exists()
    assert (output_dir / "C_overmatch_taxonomy.md").exists()
    assert (output_dir / "C_candidate_comparison.md").exists()
    assert (output_dir / "C_source_agreement.md").exists()


def test_c_heldout_실패는_예약을_남기고_재실행을_막는다(monkeypatch, tmp_path):
    import eval.run_eval as run_eval

    cases, _ = _sw_cases_and_baseline()
    output_dir = tmp_path / "C"
    output_dir.mkdir()
    (output_dir / "tuning-result.json").write_text('{"passed": true}', encoding="utf-8")
    approval = tmp_path / "approval.json"
    approval.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run_eval, "EXPERIMENT_C_DIR", output_dir)
    monkeypatch.setattr(run_eval, "EXPERIMENT_C_BASELINE", tmp_path / "baseline.json")
    monkeypatch.setattr(run_eval, "validate_baseline_inputs", lambda *_args: {})
    monkeypatch.setattr(run_eval, "_load_golden", lambda _version: cases)
    monkeypatch.setattr(run_eval, "validate_generic_approval_repository_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_eval, "validate_c_approval", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_eval, "_git_runtime_tree", lambda: "tree")
    monkeypatch.setattr(run_eval, "_run_track_a", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        run_eval._run_experiment_c("held-out", approval_file=str(approval))
    record = json.loads((output_dir / "heldout-run.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED"
