"""실험 S 거버넌스 게이트의 결정론적 계약 테스트."""
import json

import pytest


def _cases(n=54):
    return [{"case_id": f"c-{i:02d}"} for i in range(n)]


def test_실험_S_분할은_36_18건이고_순서를_보존한다():
    from eval.experiment_s import split_cases

    result = split_cases(_cases(), {"heldout_case_ids": [f"c-{i:02d}" for i in range(36, 54)]})
    assert len(result["tuning"]) == 36
    assert len(result["held-out"]) == 18
    assert result["tuning"][0]["case_id"] == "c-00"
    assert result["held-out"][-1]["case_id"] == "c-53"


def test_case_ids로_heldout을_우회할_수_없다():
    from eval.experiment_s import ensure_case_ids_allowed

    with pytest.raises(ValueError, match="held-out"):
        ensure_case_ids_allowed({"held"}, heldout_ids={"held"}, split=None)
    with pytest.raises(ValueError, match="함께"):
        ensure_case_ids_allowed({"tune"}, heldout_ids={"held"}, split="tuning")


def test_승인_파일은_입력_해시와_코드_식별자를_검증한다():
    from eval.experiment_s import validate_approval

    approval = {
        "experiment_id": "S", "baseline_commit": "base", "code_commit": "code",
        "manifest_sha256": "manifest", "tuning_report_sha256": "tuning",
        "approved_by": "reviewer", "approved_at": "2026-07-13T00:00:00+09:00",
        "allowed_split": "held-out",
    }
    validate_approval(approval, manifest_sha256="manifest", tuning_report_sha256="tuning", code_commit="code")
    with pytest.raises(ValueError, match="해시"):
        validate_approval(approval, manifest_sha256="other", tuning_report_sha256="tuning", code_commit="code")


def test_tuning_heldout_통과_조건은_엄격한_초과를_사용한다():
    from eval.experiment_s import heldout_passed, tuning_passed

    assert tuning_passed({"fn": 7, "fp": 5, "f1": 0.5631})
    assert not tuning_passed({"fn": 7, "fp": 5, "f1": 0.563})
    assert heldout_passed({"fn": 6, "fp": 1, "f1": 0.3641})
    assert not heldout_passed({"fn": 6, "fp": 1, "f1": 0.364})


def test_기실행_기록이_있으면_실패한다(tmp_path):
    from eval.experiment_s import validate_run_record_absent

    path = tmp_path / "heldout-run.json"
    path.write_text(json.dumps({"immutable": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="이미 존재"):
        validate_run_record_absent(path)


def test_예약은_원자적으로_선점되고_실패해도_재실행을_막는다(tmp_path):
    from eval.experiment_s import reserve_run_record, update_run_record

    path = tmp_path / "heldout-run.json"
    reserve_run_record(path, {"status": "STARTED"})
    with pytest.raises(ValueError, match="이미 존재"):
        reserve_run_record(path, {"status": "STARTED"})
    update_run_record(path, {"status": "FAILED"})
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "FAILED"


def test_일반_v4_CLI도_heldout_case_id를_차단한다(monkeypatch):
    import eval.run_eval as run_eval

    monkeypatch.setattr(run_eval, "_run_track_a", lambda *args, **kwargs: pytest.fail("평가가 실행되면 안 됩니다"))
    with pytest.raises(ValueError, match="held-out"):
        run_eval.main(track="a", version="v4", case_ids={"v4-si-13"}, write_output=False)


def test_heldout_평가_전에_예약하고_실패_상태를_남긴다(monkeypatch, tmp_path):
    import eval.run_eval as run_eval

    ids = [f"case-{i:02d}" for i in range(54)]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"heldout_case_ids": ids[36:]}), encoding="utf-8")
    monkeypatch.setattr(run_eval, "EXPERIMENT_S_MANIFEST", manifest_path)
    monkeypatch.setattr(run_eval, "EXPERIMENT_S_DIR", tmp_path / "S")
    monkeypatch.setattr(run_eval, "_load_golden", lambda _version: [{"case_id": case_id} for case_id in ids])
    (tmp_path / "S").mkdir()
    (tmp_path / "S" / "tuning-result.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
    approval = tmp_path / "approval.json"
    approval.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run_eval, "validate_approval_repository_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_eval, "validate_approval", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_eval, "_git_commit", lambda: "code")
    monkeypatch.setattr(run_eval, "_run_track_a", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        run_eval._run_experiment_s("held-out", approval_file=str(approval))
    record = json.loads((tmp_path / "S" / "heldout-run.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED"
