"""eval 전용 case-level 진단 덤프의 결정론적 규격 테스트."""
from types import SimpleNamespace


def _standard(clause_id="std-1", version="2025", category="PAYMENT"):
    return SimpleNamespace(clause_id=clause_id, version=version, category=category)


def test_case_diagnostics는_독소_top3와_이탈_매칭근거를_보존한다():
    from eval.diagnostics import build_case_diagnostics

    golden_by_type = {
        "SI_SUBCONTRACT": [
            {
                "case_id": "extra-overmatch",
                "gold_deviation": "EXTRA",
                "gold_toxic": ["IP_TOTAL_FREE"],
                "trap": "contradiction",
            },
            {
                "case_id": "normal-fp-toxic",
                "gold_deviation": "NONE",
                "gold_toxic": [],
                "trap": "none",
            },
        ]
    }
    review_results = {
        "SI_SUBCONTRACT": {
            "extra-overmatch": SimpleNamespace(
                deviation="NONE", confidence=0.91, matched_standard=_standard(), toxic_patterns=[]
            ),
            "normal-fp-toxic": SimpleNamespace(
                deviation="NONE", confidence=0.88, matched_standard=_standard("std-2"),
                toxic_patterns=["NONCOMPETE_EXCESS"],
            ),
        }
    }
    toxic_hits = {
        "SI_SUBCONTRACT": {
            "extra-overmatch": [
                {"id": "toxic-ip-1", "pattern": "IP_TOTAL_FREE", "rerank_score": 0.59},
                {"id": "toxic-other", "pattern": "NONCOMPETE_EXCESS", "rerank_score": 0.40},
            ],
            "normal-fp-toxic": [
                {"id": "toxic-nc-1", "pattern": "NONCOMPETE_EXCESS", "rerank_score": 0.80},
            ],
        }
    }
    standard_hits = {
        "SI_SUBCONTRACT": {
            "extra-overmatch": [{"id": "std-1", "rerank_score": 0.91, "source": "standard_clauses"}],
            "normal-fp-toxic": [{"id": "std-2", "rerank_score": 0.88, "source": "standard_sub_chunks"}],
        }
    }

    diagnostics = build_case_diagnostics(
        golden_by_type, review_results, toxic_hits, standard_hits,
        match_threshold=0.5, toxic_threshold=0.6,
    )

    deviation = diagnostics["deviation"][0]
    assert deviation["case_id"] == "extra-overmatch"
    assert deviation["outcome"] == "FN"
    assert deviation["reason"] == "OVER_MATCH"
    assert deviation["matched_standard"]["version"] == "2025"
    assert deviation["top_candidates"][0]["source"] == "standard_clauses"
    assert deviation["predicted_by_threshold"]["0.50"] is False

    toxic = diagnostics["toxic"]
    assert toxic[0]["case_id"] == "extra-overmatch"
    assert toxic[0]["outcome"] == "FN"
    assert toxic[0]["reason"] == "BELOW_THRESHOLD"
    assert toxic[0]["top_candidates"][0]["pattern_id"] == "toxic-ip-1"
    assert toxic[0]["predicted_by_threshold"]["0.60"] == []
    assert toxic[1]["outcome"] == "FP"
    assert toxic[1]["reason"] == "WRONG_PATTERN"


def test_case_diagnostics는_후보없음을_명시표식으로_남긴다():
    from eval.diagnostics import build_case_diagnostics

    diagnostics = build_case_diagnostics(
        {"SW_FREELANCE": [{"case_id": "missing", "gold_deviation": "EXTRA", "gold_toxic": ["IP_TOTAL_FREE"], "trap": "none"}]},
        {"SW_FREELANCE": {"missing": SimpleNamespace(deviation="NO_MATCH", confidence=0.0, matched_standard=None, toxic_patterns=[])}},
        {"SW_FREELANCE": {"missing": []}},
        {"SW_FREELANCE": {"missing": []}},
    )

    assert diagnostics["deviation"][0]["reason"] == "NO_CANDIDATE"
    assert diagnostics["deviation"][0]["top_candidates"] == []
    assert diagnostics["toxic"][0]["reason"] == "SEARCH_MISS"


def test_diagnostic_reports는_json과_markdown을_결정론적으로_작성한다(tmp_path):
    from eval.diagnostics import write_case_diagnostics

    diagnostics = {
        "deviation": [{"case_id": "b", "contract_type": "SI_SUBCONTRACT", "outcome": "FP", "reason": "UNDER_MATCH"}],
        "toxic": [{"case_id": "a", "contract_type": "SW_FREELANCE", "outcome": "FN", "reason": "SEARCH_MISS"}],
    }
    paths = write_case_diagnostics("v9", diagnostics, str(tmp_path))

    assert paths["json"].endswith("v9_diagnostics.json")
    assert '"case_id": "b"' in (tmp_path / "v9_diagnostics.json").read_text(encoding="utf-8")
    markdown = (tmp_path / "v9_diagnostics.md").read_text(encoding="utf-8")
    assert "이탈 case-level 진단" in markdown
    assert "SEARCH_MISS" in markdown


def test_tracing_reranker는_실제_표준과_서브청크_후보를_출처와_함께_보존한다():
    from eval.run_eval import _TracingReranker

    class FakeReranker:
        def rerank_many(self, _queries, hits_per_query, text_key, top_k):
            assert text_key == "text"
            assert top_k == 3
            return hits_per_query

    tracer = _TracingReranker(FakeReranker())
    tracer.rerank_many(["q"], [[{"id": "standard", "rerank_score": 0.7}]], "text", 3)
    tracer.rerank_many(
        ["q"], [[{"id": "sub", "parent_clause_id": "parent", "rerank_score": 0.9}]], "text", 3
    )
    candidates = tracer.candidates_by_case([{"case_id": "case"}])

    assert [candidate["id"] for candidate in candidates["case"]] == ["sub", "standard"]
    assert [candidate["source"] for candidate in candidates["case"]] == [
        "standard_sub_chunks", "standard_clauses"
    ]


def test_tracing_reranker는_독소_후보의_원문과_rerank_text를_보존한다():
    from eval.run_eval import _TracingReranker

    class FakeReranker:
        def rerank_many(self, _queries, hits_per_query, text_key, top_k):
            assert text_key == "rerank_text"
            return [[{**hit, "rerank_score": 0.8} for hit in hits] for hits in hits_per_query]

    tracer = _TracingReranker(FakeReranker())
    tracer.rerank_many(
        ["q"],
        [[{
            "id": "toxic-1", "pattern": "IP_TOTAL_FREE", "text": "원문",
            "rerank_text": "검토 패턴: 제목\n예문: 원문",
        }]],
        "rerank_text", 3,
    )
    candidates = tracer.toxic_candidates_by_case([{"case_id": "case"}])

    assert candidates["case"][0]["text"] == "원문"
    assert candidates["case"][0]["rerank_text"].startswith("검토 패턴: 제목")
