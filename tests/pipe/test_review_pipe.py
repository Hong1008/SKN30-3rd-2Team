"""
[작업 규격 · 담당: 팀원 C + 리드] pipe.review_pipe — review_contract 조립

개정 사항: 1차 판정을 매칭 임계값 단일 기준으로 전면 단순화하여 CHANGED 및 커버리지 2패스를 삭제.
이에 따라 관련 커버리지 테스트들이 제거되었습니다.
"""
from typing import Any, Dict, List

from contracts.enums import ContractType, Category, Deviation, ToxicPattern, ProgressPhase
from contracts.models import Clause, StandardClause, GroundingLaw, DeviationResult
from pipe.review_pipe import review_contract


# --- 표준조항 코퍼스 ---
ART20 = StandardClause(
    clause_id="sw_freelance-art20", contract_type=ContractType.SW_FREELANCE,
    category=Category.IP_OWNERSHIP, title="지식재산권의 귀속",
    text="결과물에 대한 지식재산권은 수급인과 도급인의 공동소유로 한다.",
    source="s/제20조", version="2020",
)
ART99_UNMATCHED = StandardClause(
    clause_id="sw_freelance-art99", contract_type=ContractType.SW_FREELANCE,
    category=Category.DISPUTE, title="관할법원", text="분쟁은 관할 법원에서 해결한다.",
    source="s/제99조", version="2020",
)
ALL_STANDARD = [ART20, ART99_UNMATCHED]

_ART20_HIT = {
    "id": "sw_freelance-art20", "text": ART20.text,
    "contract_type": "SW_FREELANCE", "category": "IP_OWNERSHIP",
    "title": ART20.title, "source": ART20.source, "version": "2020",
    "fusion_score": 0.03,
}
_TOXIC_HIT = {
    "id": "toxic-ip_total_free-01", "text": "저작권 등 일체의 권리를 전부 무상으로 양도한다.",
    "pattern": "IP_TOTAL_FREE", "category": "IP_OWNERSHIP", "title": "IP 전부 무상 귀속",
}


class FakeRetriever:
    """컬렉션·질의별 고정 결과를 반환하는 검색 포트 fake (hybrid_search_many 로 배치 검색)."""
    def _search_one(self, collection_name: str, query: str) -> List[Dict[str, Any]]:
        if collection_name == "standard_clauses":
            if "저작권" in query or "지식재산" in query:
                return [dict(_ART20_HIT)]
            return []
        if collection_name == "toxic_patterns":
            if "무상" in query:
                return [dict(_TOXIC_HIT)]
            return []
        return []

    def hybrid_search_many(self, collection_name, vectors, queries, metadata_filter=None, top_k=5):
        return [self._search_one(collection_name, q) for q in queries]


class FakeSubChunkRetriever(FakeRetriever):
    """standard_clauses 는 비고, standard_sub_chunks 만 art20 부모로 히트."""
    def _search_one(self, collection_name, query):
        if collection_name == "standard_sub_chunks" and ("저작권" in query or "지식재산" in query):
            return [{"id": "sw_freelance-art20-sub01", "text": ART20.text,
                     "parent_clause_id": "sw_freelance-art20", "sub_chunk_index": 0}]
        if collection_name == "standard_clauses":
            return []  # 조항 레벨은 일부러 미스
        return super()._search_one(collection_name, query)


class FakeEmbedder:
    """검색 fake 가 벡터 값 자체는 쓰지 않으므로, 텍스트 수만큼 더미 벡터를 반환한다."""
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.0]

    def compute_similarity(self, query: str, documents: List[str]) -> List[float]:
        return [0.0] * len(documents)


class _Reranker:
    """모든 후보에 고정 점수를 부여하는 리랭커 fake.

    실제 BgeReranker(CrossEncoder, num_labels=1)는 predict() 내부에서 이미 Sigmoid를
    적용해 0~1 확률값을 반환하므로, fake도 로짓이 아니라 그 확률값을 직접 준다.
    """
    def __init__(self, score: float):
        self._score = score

    def compute_scores(self, query, documents):
        return [self._score] * len(documents)

    def compute_scores_many(self, queries, docs_per_query):
        return [self.compute_scores(q, docs) for q, docs in zip(queries, docs_per_query)]

    def rerank(self, query, items, text_key="text", top_k=None):
        out = [{**it, "rerank_score": self._score} for it in items]
        out.sort(key=lambda x: x["rerank_score"], reverse=True)
        return out[:top_k] if top_k is not None else out

    def rerank_many(self, queries, items_per_query, text_key="text", top_k=None):
        return [
            self.rerank(q, items, text_key=text_key, top_k=top_k)
            for q, items in zip(queries, items_per_query)
        ]


class _CapturingReranker(_Reranker):
    def __init__(self, score: float):
        super().__init__(score)
        self.calls = []

    def rerank_many(self, queries, items_per_query, text_key="text", top_k=None):
        self.calls.append((text_key, items_per_query))
        return super().rerank_many(queries, items_per_query, text_key=text_key, top_k=top_k)


HIGH_RERANKER = _Reranker(0.9997)  # 매칭 인정 (match_threshold=0.5 이상)
LOW_RERANKER = _Reranker(0.0003)   # 임계 미달


class FakeGrounder:
    def get_grounding(self, _category: Category, _contract_type=None) -> List[GroundingLaw]:
        return [GroundingLaw(법령명="저작권법", 조번호="제5조", 본문="...", 출처="국가법령정보")]

    def query_law(self, _clause_text: str) -> List[GroundingLaw]:
        return []


def _review(clauses, retriever=None, reranker=HIGH_RERANKER):
    return review_contract(
        clauses, ContractType.SW_FREELANCE,
        retriever=retriever or FakeRetriever(),
        embedder=FakeEmbedder(),
        reranker=reranker,
        grounder=FakeGrounder(),
        all_standard_clauses=ALL_STANDARD,
    )


def test_반환은_DeviationResult_리스트():
    results = _review([Clause(idx=1, num="제5조", title="저작권", text="저작권 귀속은 회사에 있다")])
    assert isinstance(results, list)
    assert all(isinstance(r, DeviationResult) for r in results)


def test_독소_리랭커만_rerank_text와_원문을_함께_받는다():
    reranker = _CapturingReranker(0.9)
    _review(
        [Clause(idx=1, num="제5조", title="저작권", text="저작권 전부 무상")],
        reranker=reranker,
    )

    toxic_call = next(items for text_key, items in reranker.calls if text_key == "rerank_text")
    assert toxic_call[0][0]["text"] == _TOXIC_HIT["text"]
    assert toxic_call[0][0]["rerank_text"].startswith("검토 패턴: IP 전부 무상 귀속\n예문: ")


def test_검색결과_없으면_NO_MATCH():
    clause = Clause(idx=1, num="제9조", title="기타", text="완전히 무관한 비표준 내용")
    results = _review([clause])
    target = [r for r in results if r.user_clause == clause.text]
    assert target and target[0].deviation == Deviation.NO_MATCH


def test_후보는_있으나_임계미달이면_EXTRA():
    clause = Clause(idx=1, num="제5조", title="저작권", text="저작권 귀속은 회사에 있다")
    results = _review([clause], reranker=LOW_RERANKER)
    target = [r for r in results if r.user_clause == clause.text]
    assert target and target[0].deviation == Deviation.EXTRA
    # 2차 LLM이 "무엇과 비교해 다른지" 판단할 수 있도록 근접후보는 버리지 않는다.
    assert target[0].matched_standard is not None
    assert target[0].matched_standard.clause_id == "sw_freelance-art20"


def test_강한_매칭도_매칭되면_NONE():
    clause = Clause(idx=1, num="제5조", title="저작권", text="저작권 귀속은 회사에 있다")
    results = _review([clause])
    matched = [r for r in results if r.matched_standard and r.matched_standard.clause_id == "sw_freelance-art20"]
    assert matched
    assert matched[0].deviation == Deviation.NONE
    assert matched[0].grounding == []


def test_본문_동일하면_NONE_이고_근거없음():
    clause = Clause(idx=1, num="제20조", title="지식재산권", text=ART20.text)
    results = _review([clause])
    matched = [r for r in results if r.matched_standard and r.matched_standard.clause_id == "sw_freelance-art20"]
    assert matched and matched[0].deviation == Deviation.NONE
    assert matched[0].grounding == []


def test_매칭안된_표준조항은_MISSING():
    results = _review([Clause(idx=1, num="제5조", title="저작권", text="저작권 귀속")])
    missing_ids = [
        r.matched_standard.clause_id for r in results
        if r.deviation == Deviation.MISSING and r.matched_standard
    ]
    assert "sw_freelance-art99" in missing_ids


def test_임계미달_근접후보는_MISSING_탐지를_오염시키지_않음():
    """EXTRA로 판정된 근접후보가 있어도, 그 표준조항은 '커버됨'으로 치지 않고 MISSING으로 잡혀야 한다."""
    clause = Clause(idx=1, num="제5조", title="저작권", text="저작권 귀속은 회사에 있다")
    results = _review([clause], reranker=LOW_RERANKER)
    missing_ids = [
        r.matched_standard.clause_id for r in results
        if r.deviation == Deviation.MISSING and r.matched_standard
    ]
    assert "sw_freelance-art20" in missing_ids


def test_독소패턴_역방향검색이_toxic_patterns에_채워짐():
    clause = Clause(idx=1, num="제5조", title="저작권", text="저작권을 전부 무상으로 양도한다")
    results = _review([clause])
    target = [r for r in results if r.user_clause == clause.text]
    assert target and ToxicPattern.IP_TOTAL_FREE in target[0].toxic_patterns


def test_서브청크_rollup으로_부모조항_매칭():
    clause = Clause(idx=1, num="제20조", title="지식재산권", text=ART20.text)
    results = _review([clause], retriever=FakeSubChunkRetriever())
    matched = [r for r in results if r.matched_standard and r.matched_standard.clause_id == "sw_freelance-art20"]
    assert matched and matched[0].deviation != Deviation.NO_MATCH


def test_progress_callback_호출_검증():
    called = []
    def callback(done: int, total: int, phase: ProgressPhase):
        called.append((done, total, phase))

    clause1 = Clause(idx=1, num="제20조", title="지식재산권", text=ART20.text)
    clause2 = Clause(idx=2, num="제99조", title="관할법원", text="분쟁 관할")

    review_contract(
        [clause1, clause2], ContractType.SW_FREELANCE,
        retriever=FakeRetriever(),
        embedder=FakeEmbedder(),
        reranker=HIGH_RERANKER,
        grounder=FakeGrounder(),
        all_standard_clauses=ALL_STANDARD,
        progress_callback=callback
    )

    assert called == [
        (0, 2, ProgressPhase.PREPARE),
        (0, 2, ProgressPhase.BATCH_SEARCH),
        (0, 2, ProgressPhase.RERANK),
        (1, 2, ProgressPhase.CLAUSE_REVIEW),
        (2, 2, ProgressPhase.CLAUSE_REVIEW),
        (2, 2, ProgressPhase.MISSING_DETECTION),
    ]
