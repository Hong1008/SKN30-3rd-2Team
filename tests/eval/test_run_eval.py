"""
[작업 규격 · 담당: 팀원 D] eval.run_eval — 골든셋으로 검색/이탈 탐지 평가

구현 대상: eval/run_eval.py
  - 순수 집계 함수(테스트 대상): 이미 검색된 결과 케이스들 → 지표 묶음
        evaluate(cases: list[dict], k: int = 5) -> dict
            cases 각 항목: {"retrieved_ids": list[str], "gold_id": str}
            반환: {"recall@k": float, "mrr": float, "n": int}
  - CLI 부분(테스트 밖): 골든셋을 review 파이프에 통과시켜 retrieved_ids 를 모으고
    위 evaluate 로 집계해 리포트 출력. (실제 인덱스 필요 → 통합/수동)

eval.metrics 의 recall_at_k / mrr 를 재사용합니다. (중복 구현 금지)

👉 구현을 시작하면 pytestmark(skip) 줄을 삭제하세요.
"""
import pytest
from types import SimpleNamespace


def test_evaluate_집계():
    from eval.run_eval import evaluate
    cases = [
        {"retrieved_ids": ["a", "b", "c"], "gold_id": "a"},  # rr=1.0, recall@2=1
        {"retrieved_ids": ["x", "y", "z"], "gold_id": "z"},  # rr=1/3, recall@2=0
    ]
    report = evaluate(cases, k=2)
    assert report["n"] == 2
    assert report["recall@k"] == pytest.approx(0.5)              # 1/2 케이스만 상위2 적중
    assert report["mrr"] == pytest.approx((1.0 + 1 / 3) / 2)


def test_evaluate_빈_케이스():
    from eval.run_eval import evaluate
    report = evaluate([], k=5)
    assert report["n"] == 0


def test_임계값_보정용_고정_heldout을_분리한다():
    from eval.run_eval import split_threshold_calibration_cases

    golden = [
        {"case_id": "tuning-1", "contract_type": "SI_SUBCONTRACT"},
        {"case_id": "heldout-1", "contract_type": "SI_SUBCONTRACT"},
        {"case_id": "heldout-2", "contract_type": "SM_SUBCONTRACT"},
    ]

    split = split_threshold_calibration_cases(golden, {"heldout-1", "heldout-2"})

    assert [case["case_id"] for case in split["tuning"]] == ["tuning-1"]
    assert [case["case_id"] for case in split["heldout"]] == ["heldout-1", "heldout-2"]


def test_임계값_heldout에_없는_case_id가_있으면_실패한다():
    from eval.run_eval import split_threshold_calibration_cases

    with pytest.raises(ValueError, match="ghost"):
        split_threshold_calibration_cases(
            [{"case_id": "known", "contract_type": "SI_SUBCONTRACT"}],
            {"ghost"},
        )


def test_이탈_임계값_스윕은_confidence로_혼동행렬을_재계산한다():
    from eval.run_eval import deviation_threshold_sweep

    golden_by_type = {
        "SI_SUBCONTRACT": [
            {"case_id": "none", "gold_deviation": "NONE"},
            {"case_id": "extra", "gold_deviation": "EXTRA"},
        ]
    }
    review_results_by_type = {
        "SI_SUBCONTRACT": {
            "none": SimpleNamespace(matched_standard=object(), confidence=0.55),
            "extra": SimpleNamespace(matched_standard=object(), confidence=0.45),
        }
    }

    sweep = deviation_threshold_sweep(
        golden_by_type,
        review_results_by_type,
        thresholds=(0.5, 0.6),
    )

    assert sweep[0]["threshold"] == 0.5
    assert sweep[0]["tp"] == 1
    assert sweep[0]["tn"] == 1
    assert sweep[0]["f1"] == pytest.approx(1.0)
    assert sweep[1]["threshold"] == 0.6
    assert sweep[1]["tp"] == 1
    assert sweep[1]["fp"] == 1
    assert sweep[1]["f1"] == pytest.approx(2 / 3)


def test_독소_임계값_스윕은_임계값별_리뷰결과를_합산한다():
    from eval.run_eval import toxic_threshold_sweep

    golden_by_type = {
        "SI_SUBCONTRACT": [
            {"case_id": "normal", "gold_toxic": []},
            {"case_id": "toxic", "gold_toxic": ["IP_TOTAL_FREE"]},
        ]
    }
    toxic_hits_by_type = {
        "SI_SUBCONTRACT": {
            "normal": [{"pattern": "IP_TOTAL_FREE", "rerank_score": 0.7}],
            "toxic": [{"pattern": "IP_TOTAL_FREE", "rerank_score": 0.8}],
        }
    }

    sweep = toxic_threshold_sweep(
        golden_by_type,
        toxic_hits_by_type,
        thresholds=(0.6, 0.8),
    )

    assert sweep[0]["threshold"] == 0.6
    assert sweep[0]["tp"] == 1
    assert sweep[0]["fp"] == 1
    assert sweep[1]["threshold"] == 0.8
    assert sweep[1]["tp"] == 1
    assert sweep[1]["fp"] == 0


def test_가중치별_hybrid_변형군을_생성한다(monkeypatch):
    """A-1 스윕은 모든 권장 비율을 retriever에 전달해야 한다."""
    import adapter
    from eval.run_eval import HYBRID_WEIGHT_VARIANTS, SEARCH_VARIANTS, build_cases_by_variant

    class FakeVector:
        def __init__(self):
            self.hybrid_calls = []

        def bm25_search_many(self, _collection, queries, _filter, _top_k):
            return [[{"id": "bm25-hit", "text": query}] for query in queries]

        def dense_search_many(self, _collection, vectors, _filter, _top_k):
            return [[{"id": "dense-hit", "text": str(vector)}] for vector in vectors]

        def hybrid_search_many(
            self, _collection, _vectors, queries, _filter, _top_k,
            dense_weight=1.0, bm25_weight=1.0,
        ):
            self.hybrid_calls.append((dense_weight, bm25_weight))
            return [[{"id": f"hybrid-{dense_weight:g}-{bm25_weight:g}", "text": query}] for query in queries]

    class FakeEmbedder:
        def embed_documents(self, texts):
            return [[float(index)] for index, _ in enumerate(texts)]

    class FakeReranker:
        def rerank_many(self, _queries, hits_per_query, text_key, top_k):
            assert text_key == "text"
            assert top_k == 5
            return hits_per_query

    fake_vector = FakeVector()
    monkeypatch.setattr(adapter, "vector", fake_vector)
    monkeypatch.setattr(adapter, "embedder", FakeEmbedder())
    monkeypatch.setattr(adapter, "reranker", FakeReranker())

    result = build_cases_by_variant(
        [{"user_clause": "제1조 테스트", "gold_clause_id": "gold"}],
        k=5,
        contract_type="SW_FREELANCE",
    )

    assert tuple(result) == SEARCH_VARIANTS
    assert fake_vector.hybrid_calls == [
        (dense_weight, bm25_weight)
        for _, dense_weight, bm25_weight in HYBRID_WEIGHT_VARIANTS
    ]
    assert result["hybrid_7_3"][0]["retrieved_ids"] == ["hybrid-7-3"]
    assert result["hybrid_rerank_9_1"][0]["gold_id"] == "gold"


# --- 축퇴 경보 (v1 리뷰 §1 사후 조치: recall 1.0 / 특이도 0 오독을 지표 차원에서 차단) ---
def _scores(tp, fp, fn, tn):
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def test_degeneracy_alerts_전부_양성이면_경보():
    from eval.run_eval import degeneracy_alerts
    assert degeneracy_alerts(_scores(tp=5, fp=4, fn=0, tn=0), "이탈") != []


def test_degeneracy_alerts_전부_음성이면_경보():
    from eval.run_eval import degeneracy_alerts
    assert degeneracy_alerts(_scores(tp=0, fp=0, fn=3, tn=4), "독소") != []


def test_degeneracy_alerts_정상_분포면_경보_없음():
    from eval.run_eval import degeneracy_alerts
    assert degeneracy_alerts(_scores(tp=3, fp=1, fn=1, tn=4), "이탈") == []


def test_degeneracy_alerts_빈_집계는_경보_없음():
    from eval.run_eval import degeneracy_alerts
    assert degeneracy_alerts(_scores(tp=0, fp=0, fn=0, tn=0), "이탈") == []


def test_coverage_degeneracy_단일_클래스면_경보():
    from eval.run_eval import coverage_degeneracy_alert
    assert coverage_degeneracy_alert({"EXTRA": 10}) is not None


def test_coverage_degeneracy_혼합_분포면_경보_없음():
    from eval.run_eval import coverage_degeneracy_alert
    assert coverage_degeneracy_alert({"EXTRA": 6, "NONE": 4}) is None


def test_coverage_degeneracy_표본_너무_작으면_판단_보류():
    from eval.run_eval import coverage_degeneracy_alert
    assert coverage_degeneracy_alert({"EXTRA": 2}) is None


def test_load_golden은_진단_산출물을_골든케이스로_읽지_않는다(tmp_path):
    import json
    from eval.run_eval import _load_golden

    (tmp_path / "v9_sw_freelance.json").write_text(
        json.dumps([{"case_id": "case", "contract_type": "SW_FREELANCE"}]), encoding="utf-8"
    )
    (tmp_path / "v9_diagnostics.json").write_text(json.dumps({"deviation": []}), encoding="utf-8")

    assert _load_golden("v9", str(tmp_path)) == [{"case_id": "case", "contract_type": "SW_FREELANCE"}]
