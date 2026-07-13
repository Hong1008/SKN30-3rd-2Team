"""
[담당: 팀원 D] 골든셋으로 검색/이탈 탐지 평가 (기획서 8)

규격(통과해야 할 테스트): tests/eval/test_run_eval.py
순수 집계 함수 evaluate 는 eval.metrics 를 재사용합니다(중복 구현 금지).

Driver(트랙 A, 통합/수동 실행 — 단위테스트 밖): 골든셋(src/eval/golden/*.json)의 user_clause 를
실제 어댑터(vector·reranker)와 review_contract 전체 파이프에 흘려 cases 를 만들고,
run_eval.evaluate / eval.ablation.run_ablation / eval.metrics.precision_recall 로 집계합니다.
규격: docs/tasks/D_eval.md §Driver.
"""
import sys
import logging
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)



from core.splitter import normalize_for_search
from core import prepare_toxic_rerank_candidates
from eval import metrics
from eval.experiment_s import (
    BASELINE_COMMIT,
    EXPERIMENT_ID,
    VERSION as EXPERIMENT_VERSION,
    build_confusion_summary,
    build_top3_diff,
    ensure_case_ids_allowed,
    heldout_passed,
    load_manifest,
    sha256_file,
    split_cases,
    tuning_passed,
    validate_approval,
    validate_approval_repository_state,
    validate_run_record_absent,
    reserve_run_record,
    update_run_record,
)
from eval.experiment_c import (
    BASELINE_DIAGNOSTICS_PATH as EXPERIMENT_C_BASELINE_DIAGNOSTICS,
    BASELINE_PATH as EXPERIMENT_C_BASELINE,
    CASE_MATRIX_PATH as EXPERIMENT_C_CASE_MATRIX,
    EXPERIMENT_C,
    MANIFEST_PATH as EXPERIMENT_C_MANIFEST,
    classify_overmatch,
    split_sw_cases,
    validate_baseline_inputs,
    validate_c_approval,
    write_taxonomy,
)
from eval.experiment_governance import passed, validate_approval_repository_state as validate_generic_approval_repository_state


def evaluate(cases: List[Dict], k: int = 5) -> Dict:
    """
    검색 결과 케이스들을 지표로 집계합니다.
    cases 각 항목: {"retrieved_ids": list[str], "gold_id": str}
    반환: {"recall@k": float, "mrr": float, "n": int}
    """
    if not cases:
        return {"recall@k": 0.0, "mrr": 0.0, "n": 0}

    n = len(cases)
    logger.info(f"[evaluate] 지표 집계 시작: n={n}건 (k={k})")

    # 1. Recall@K 집계
    recalls = [
        metrics.recall_at_k(c["retrieved_ids"], c["gold_id"], k)
        for c in cases
    ]
    avg_recall = sum(recalls) / n

    # 2. MRR 집계
    # metrics.mrr은 (retrieved_ids, gold_id) 튜플 리스트를 입력으로 받음
    rr_cases = [(c["retrieved_ids"], c["gold_id"]) for c in cases]
    avg_mrr = metrics.mrr(rr_cases)

    return {
        "recall@k": avg_recall,
        "mrr": avg_mrr,
        "n": n
    }


def degeneracy_alerts(scores: Dict[str, float], label: str) -> List[str]:
    """이진 분류 집계에서 '전 케이스 단일 판정' 축퇴를 감지합니다 (v1 리뷰 §1 사후 조치).

    v1 에서 recall=1.0 이 "완벽"이 아니라 전 조항을 양성으로 찍은 축퇴였음이 특이도=0 으로야
    드러났습니다. 같은 오독이 재발하지 않도록, 예측이 한 클래스로 쏠리면 지표 옆에 경보를 답니다.
    scores: metrics.binary_scores 반환값 (tp/fp/fn/tn 포함). 반환: 경보 문구 목록(정상이면 빈 목록).
    """
    n = scores["tp"] + scores["fp"] + scores["fn"] + scores["tn"]
    if not n:
        return []
    positive_predictions = scores["tp"] + scores["fp"]
    if positive_predictions == n:
        return [
            f"⚠️ 축퇴 의심({label}): 검토된 전 케이스({n:.0f}건)를 양성으로 판정 — "
            "recall 1.0 은 성능이 아니라 '다 찍음'일 수 있음 (특이도 확인)"
        ]
    if positive_predictions == 0:
        return [
            f"⚠️ 축퇴 의심({label}): 검토된 전 케이스({n:.0f}건)를 음성으로 판정 — "
            "임계값이 지나치게 높거나 분류기가 무신호일 수 있음"
        ]
    return []


# 트랙 B 는 문서당 조항이 적으므로, 이 수 미만이면 단일 클래스여도 축퇴로 단정하지 않는다
_COVERAGE_DEGENERACY_MIN_N = 3


def coverage_degeneracy_alert(deviation_dist: Dict[str, int]) -> str | None:
    """트랙 B(라벨 없음)용 축퇴 감지: 문서의 deviation 분포가 단일 클래스로 쏠렸는지 봅니다.

    v1 트랙 B 에서 5문서·65조항 전부 CHANGED 로 찍힌 축퇴(리뷰 §3)를 결과 md 에서 바로
    보이게 하기 위한 표식. 표본이 _COVERAGE_DEGENERACY_MIN_N 미만이면 판단을 보류합니다.
    """
    n = sum(deviation_dist.values())
    if n < _COVERAGE_DEGENERACY_MIN_N or len(deviation_dist) != 1:
        return None
    only = next(iter(deviation_dist))
    return f"⚠️ 축퇴 의심: 전 조항({n}건)이 단일 분류({only}) — 분류기가 신호를 못 내고 있을 수 있음"


# ─────────────────────────────────────────────────────────────────────────
# Driver (트랙 A) — 아래부터는 외부 인덱스(Chroma)·모델에 의존하는 통합 코드입니다.
# `just build-db` 로 인덱스가 준비된 뒤에만 동작하며, 단위테스트 대상이 아닙니다.
# ─────────────────────────────────────────────────────────────────────────

STANDARD_COLLECTION = "standard_clauses"
SUB_CHUNK_COLLECTION = "standard_sub_chunks"
MATCH_THRESHOLD_SWEEP = (0.40, 0.45, 0.50, 0.55, 0.60)
TOXIC_THRESHOLD_SWEEP = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)
DEFAULT_MATCH_THRESHOLD = 0.5
DEFAULT_TOXIC_THRESHOLD = 0.6
# dense 단독이 동일가중 hybrid보다 우세했던 v3 결과를 검증하기 위한 RRF 비율 스윕이다.
# 5:5는 기존 기준선, 7:3·8:2·9:1은 BM25 기여를 단계적으로 낮춰 dense 우세 가설을 확인한다.
# 10:0은 dense 변형과 중복이므로 별도 hybrid 행을 만들지 않는다.
HYBRID_WEIGHT_VARIANTS = (
    ("hybrid_5_5", 5.0, 5.0),
    ("hybrid_7_3", 7.0, 3.0),
    ("hybrid_8_2", 8.0, 2.0),
    ("hybrid_9_1", 9.0, 1.0),
)
SEARCH_VARIANTS = ("bm25", "dense") + tuple(
    variant
    for hybrid_name, _, _ in HYBRID_WEIGHT_VARIANTS
    for variant in (hybrid_name, hybrid_name.replace("hybrid_", "hybrid_rerank_", 1))
)


class _MemoizingEmbedder:
    """[eval 드라이버 전용] 임베더를 감싸 텍스트별로 임베딩을 캐시하는 국소 래퍼.

    골든셋은 고정·유계인데 A-1(dense·hybrid·hybrid_rerank)과 A-2(std·sub·toxic 컬렉션)가
    동일 조항을 반복 임베딩한다(프로덕션 기준 조항당 encode 6회). 드라이버가 도는 동안에만
    텍스트→벡터를 재사용해 이 중복을 없앤다. 프로덕션 싱글톤에 전역 캐시를 심으면 무한 증가·
    스레드 경쟁을 떠안으므로, 여기서는 단일 스레드 드라이버 실행 범위로 캐시를 국소화한다.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._cache: Dict[str, List[float]] = {}

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # 캐시에 없는 텍스트만 중복 제거해 한 번에 배치 임베딩한 뒤, 요청 순서대로 복원한다.
        missing = list(dict.fromkeys(t for t in texts if t not in self._cache))
        if missing:
            for text, vector in zip(missing, self._inner.embed_documents(missing)):
                self._cache[text] = vector
        return [self._cache[t] for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def __getattr__(self, name: str) -> Any:
        # embed 외 메서드(compute_similarity 등)는 원본 임베더에 그대로 위임한다.
        return getattr(self._inner, name)


def _install_eval_embedding_cache() -> None:
    """공유 embedder 싱글톤을 드라이버 실행 동안 캐싱 래퍼로 교체한다.

    A-1·A-2 가 모두 `from adapter import embedder` 로 같은 싱글톤을 쓰므로, 여기 한 곳만
    감싸면 전체 실행이 하나의 캐시를 공유해 골든 조항을 딱 한 번만 임베딩한다.
    이미 래핑돼 있으면(중복 호출) 그대로 둔다.
    (VectorManager 는 더 이상 Embedder 에 의존하지 않으므로 adapter.embedder 자체를 감싼다.)
    """
    import adapter

    if not isinstance(adapter.embedder, _MemoizingEmbedder):
        adapter.embedder = _MemoizingEmbedder(adapter.embedder)


class NullGrounder:
    """평가 전용 no-op Grounder. review_contract 는 grounder 를 필수로 요구하지만,
    법령 근거 텍스트 자체는 결정론적 검색/분류 평가(deviation·toxic P/R) 대상이 아니므로
    외부 korean-law-mcp 호출을 생략해 평가 속도를 지키고 네트워크 의존을 없앤다.
    """

    def get_grounding(self, _category: Any, _contract_type: Any = None) -> list:
        return []

    def query_law(self, _clause_text: str) -> list:
        return []


def build_cases_by_variant(golden: List[Dict], k: int, contract_type: str) -> Dict[str, List[Dict]]:
    """A-1 검색 변형군의 (retrieved_ids, gold_id) cases 를 한 번에 만듭니다.

    EXTRA(gold_clause_id=null) 케이스는 검색 정답이 없으므로 제외합니다.
    질의별 개별 search 대신 search_many/rerank_many 배치를 써서 임베딩 왕복을 N회→1회로
    줄입니다(07-01 결정 로그 §7 — search_many 도입 취지와 동일한 이유).
    각 dense:BM25 RRF 비율은 k*4 후보 풀을 만들고, 같은 풀로 hybrid 상위 k와
    hybrid_rerank 재정렬 결과를 함께 계산한다. 따라서 융합 순위와 reranker 후보 풀 변화가
    모두 A-1에 드러난다.
    """
    from adapter import vector, reranker, embedder  # 지연 임포트: 모델 로드는 driver 실행 시에만

    scored = [g for g in golden if g.get("gold_clause_id") is not None]
    if not scored:
        return {variant: [] for variant in SEARCH_VARIANTS}

    logger.info(f"[build_cases_by_variant] 검색 케이스 생성 중 (k={k}, contract_type={contract_type}, 대상 조항={len(scored)}건)...")
    # review_contract 경로(review_golden_clauses)와 동일하게 검색·임베딩 입력은 정규화된 사본을
    # 쓴다 — 코퍼스(build_index.py)는 이미 정규화돼 있어 원문 그대로 넘기면 비대칭이 발생한다
    # (07-09 결정 로그, P_text_normalization.md).
    queries = [normalize_for_search(g["user_clause"]) for g in scored]
    gold_ids = [g["gold_clause_id"] for g in scored]
    type_filter = {"contract_type": contract_type}

    def _to_cases(hits_per_query: List[List[Dict]]) -> List[Dict]:
        return [
            {"retrieved_ids": [h["id"] for h in hits], "gold_id": gid}
            for gid, hits in zip(gold_ids, hits_per_query)
        ]

    bm25 = vector.bm25_search_many(STANDARD_COLLECTION, queries, type_filter, k)

    # dense·hybrid 가 같은 벡터를 공유하도록 임베딩은 여기서 1회만 계산한다.
    vectors = embedder.embed_documents(queries)
    dense = vector.dense_search_many(STANDARD_COLLECTION, vectors, type_filter, k)

    cases_by_variant = {
        "bm25": _to_cases(bm25),
        "dense": _to_cases(dense),
    }
    for hybrid_name, dense_weight, bm25_weight in HYBRID_WEIGHT_VARIANTS:
        pool = vector.hybrid_search_many(
            STANDARD_COLLECTION,
            vectors,
            queries,
            type_filter,
            k * 4,
            dense_weight=dense_weight,
            bm25_weight=bm25_weight,
        )
        cases_by_variant[hybrid_name] = _to_cases([hits[:k] for hits in pool])
        rerank_name = hybrid_name.replace("hybrid_", "hybrid_rerank_", 1)
        reranked = reranker.rerank_many(queries, pool, text_key="text", top_k=k)
        cases_by_variant[rerank_name] = _to_cases(reranked)

    return cases_by_variant


def _load_standards(contract_type: str) -> List[Any]:
    """server.py `_load_standards(ct)` 와 동일한 패턴으로 계약 유형별 표준조항 전체를 로드합니다."""
    from adapter import db
    from contracts.models import StandardClause

    rows = db.fetch_all(
        "SELECT * FROM standard_clauses WHERE contract_type = ?",
        contract_type,
    )
    return [StandardClause(**row) for row in rows]





def review_golden_clauses(
    golden: List[Dict],
    contract_type: str,
) -> Dict[str, Any]:
    """골든 케이스 전체를 review_contract 로 **한 번에** 배치 검토해 case_id → DeviationResult 를 모읍니다.

    조항별로 review_contract 를 개별 호출하면 배치 크기가 항상 1이 되어 내부의
    search_many/rerank 배치화 이점이 사라집니다(07-01 §7). 그래서 계약 유형별로 전체
    골든 조항을 한 번에 review_contract 에 태우고, 반환된 결과에서 user_clause 텍스트가
    일치하는 항목만 추립니다. review_contract 는 매칭 안 된 나머지 표준조항을 MISSING
    (user_clause="") 으로 함께 반환하므로 자연히 제외됩니다.
    """
    from adapter import vector, reranker, embedder
    from contracts.enums import ContractType
    from contracts.models import Clause
    from pipe.review_pipe import review_contract

    ct = ContractType(contract_type)
    standards = _load_standards(contract_type)
    grounder = NullGrounder()

    clauses = [
        Clause(idx=i + 1, num="", title="", text=g["user_clause"])
        for i, g in enumerate(golden)
    ]
    logger.info(f"[review_golden_clauses] 골든셋 조항 배치 검토 시작: contract_type={contract_type}, 조항={len(clauses)}개...")
    review_results = review_contract(
        clauses, ct,
        retriever=vector,
        embedder=embedder,
        reranker=reranker,
        grounder=grounder,
        all_standard_clauses=standards,
    )

    by_text: Dict[str, Any] = {}
    for r in review_results:
        if r.user_clause:  # MISSING 결과(user_clause="")는 골든 케이스가 아니므로 제외
            by_text.setdefault(r.user_clause, r)

    return {
        g["case_id"]: by_text[g["user_clause"]]
        for g in golden
        if g["user_clause"] in by_text
    }


def deviation_scores(golden: List[Dict], review_results: Dict[str, Any]) -> Dict[str, float]:
    """이탈 탐지 이진 지표(참음성 포함): 예측 = deviation != NONE, 정답 = gold_deviation != NONE.

    채점 대상(universe)은 실제 검토된 case_id 로 한정한다. specificity 가 낮으면
    정상 조항(gold_deviation="NONE")까지 이탈로 찍고 있다는 뜻 — recall 1.0 이 축퇴인지 판별한다.
    """
    from contracts.enums import Deviation

    universe = set(review_results.keys())
    predicted = {cid for cid, r in review_results.items() if r.deviation != Deviation.NONE}
    gold = {g["case_id"] for g in golden if g["gold_deviation"] != "NONE"}
    return metrics.binary_scores(predicted, gold, universe)


def toxic_scores(golden: List[Dict], review_results: Dict[str, Any]) -> Dict[str, float]:
    """독소 탐지 이진 지표(참음성 포함): 예측 = toxic_patterns 비어있지 않음, 정답 = gold_toxic 존재."""
    universe = set(review_results.keys())
    predicted = {cid for cid, r in review_results.items() if r.toxic_patterns}
    gold = {g["case_id"] for g in golden if g.get("gold_toxic")}
    return metrics.binary_scores(predicted, gold, universe)


def deviation_threshold_sweep(
    golden_by_type: Dict[str, List[Dict]],
    review_results_by_type: Dict[str, Dict[str, Any]],
    thresholds: tuple[float, ...] = MATCH_THRESHOLD_SWEEP,
) -> List[Dict[str, float]]:
    """기존 매칭 confidence로 match_threshold별 이탈 혼동행렬을 재계산합니다.

    현재 1차 이탈 판정은 후보가 있고 score가 임계값 이상이면 NONE, 그 외에는 이탈 표식입니다.
    `select_best_match`는 임계값 미달 EXTRA에도 최고 후보·confidence를 보존하므로, 이미 실행한
    review 결과를 재사용해 추가 검색·리랭킹 없이 임계값 효과만 결정론적으로 비교할 수 있습니다.
    """
    universe: set[str] = set()
    gold: set[str] = set()
    for contract_type, golden in golden_by_type.items():
        review_results = review_results_by_type[contract_type]
        universe.update(f"{contract_type}:{case_id}" for case_id in review_results)
        gold.update(
            f"{contract_type}:{g['case_id']}"
            for g in golden
            if g["gold_deviation"] != "NONE"
        )

    sweep: List[Dict[str, float]] = []
    for threshold in thresholds:
        predicted: set[str] = set()
        for contract_type, review_results in review_results_by_type.items():
            predicted.update(
                f"{contract_type}:{case_id}"
                for case_id, result in review_results.items()
                if result.matched_standard is None or result.confidence < threshold
            )
        sweep.append({"threshold": threshold, **metrics.binary_scores(predicted, gold, universe)})
    return sweep


def toxic_threshold_sweep(
    golden_by_type: Dict[str, List[Dict]],
    toxic_hits_by_type: Dict[str, Dict[str, List[Dict[str, Any]]]],
    thresholds: tuple[float, ...] = TOXIC_THRESHOLD_SWEEP,
) -> List[Dict[str, float]]:
    """한 번 재정렬한 독소 후보에 임계값만 바꿔 전체 혼동행렬을 계산합니다."""
    from pipe.review_pipe import _toxic_from_hits

    sweep: List[Dict[str, float]] = []
    for threshold in thresholds:
        universe: set[str] = set()
        gold: set[str] = set()
        predicted: set[str] = set()
        for contract_type, golden in golden_by_type.items():
            hits_by_case = toxic_hits_by_type[contract_type]
            universe.update(f"{contract_type}:{case_id}" for case_id in hits_by_case)
            gold.update(
                f"{contract_type}:{g['case_id']}"
                for g in golden
                if g.get("gold_toxic")
            )
            predicted.update(
                f"{contract_type}:{case_id}"
                for case_id, hits in hits_by_case.items()
                if _toxic_from_hits(hits, threshold)
            )
        sweep.append({"threshold": threshold, **metrics.binary_scores(predicted, gold, universe)})
    return sweep


def rerank_toxic_golden_clauses(golden: List[Dict], contract_type: str) -> Dict[str, List[Dict[str, Any]]]:
    """독소 후보를 한 번만 검색·재정렬해 case_id별 raw hit을 반환합니다.

    `DeviationResult`에는 임계값을 통과한 ToxicPattern만 남아 raw score가 보존되지 않습니다.
    임계값 스윕은 review_contract를 여러 번 재호출하는 대신, 동일한 `TOXIC_COLLECTION` 후보와
    rerank_score를 여기서 한 번 확보한 뒤 `_toxic_from_hits`의 임계 필터만 반복 적용합니다.
    """
    from adapter import vector, reranker, embedder
    from pipe.review_pipe import TOXIC_COLLECTION

    queries = [normalize_for_search(g["user_clause"]) for g in golden]
    vectors = embedder.embed_documents(queries)
    hits_batch = vector.hybrid_search_many(TOXIC_COLLECTION, vectors, queries, None, 3)
    reranked_batch = reranker.rerank_many(
        queries,
        [prepare_toxic_rerank_candidates(hits) for hits in hits_batch],
        text_key="rerank_text",
        top_k=3,
    )
    return {
        g["case_id"]: hits
        for g, hits in zip(golden, reranked_batch)
    }



def rerank_standard_golden_clauses(golden: List[Dict], contract_type: str) -> Dict[str, List[Dict[str, Any]]]:
    """이탈 진단용 표준·서브청크 top-3 후보와 출처를 보존합니다.

    review_contract의 반환 계약은 최종 매칭만 노출하므로, eval에서만 검색·재정렬을 한 번 더
    수행한다. 이 결과는 MCP 응답이나 1차 판정에는 사용하지 않는다.
    """
    from adapter import vector, reranker, embedder
    from pipe.review_pipe import STANDARD_COLLECTION, SUB_CHUNK_COLLECTION

    queries = [normalize_for_search(g["user_clause"]) for g in golden]
    if not queries:
        return {}
    vectors = embedder.embed_documents(queries)
    type_filter = {"contract_type": contract_type}
    standard_batch = vector.hybrid_search_many(STANDARD_COLLECTION, vectors, queries, type_filter, 3)
    sub_chunk_batch = vector.hybrid_search_many(SUB_CHUNK_COLLECTION, vectors, queries, type_filter, 3)
    standard_reranked = reranker.rerank_many(queries, standard_batch, text_key="text", top_k=3)
    sub_chunk_reranked = reranker.rerank_many(queries, sub_chunk_batch, text_key="text", top_k=3)

    by_case: Dict[str, List[Dict[str, Any]]] = {}
    for case, standard_hits, sub_chunk_hits in zip(golden, standard_reranked, sub_chunk_reranked):
        candidates = [
            *({**hit, "source": STANDARD_COLLECTION} for hit in standard_hits),
            *({**hit, "source": SUB_CHUNK_COLLECTION} for hit in sub_chunk_hits),
        ]
        candidates.sort(key=lambda hit: (-float(hit.get("rerank_score", 0.0)), str(hit.get("id", ""))))
        by_case[case["case_id"]] = candidates[:3]
    return by_case

GOLDEN_DIR = "src/eval/golden"
EXPERIMENT_S_DIR = Path("docs/experiments/S")
EXPERIMENT_S_MANIFEST = Path(GOLDEN_DIR) / "threshold_heldout.v4.json"


def _load_golden(version: str, golden_dir: str = GOLDEN_DIR) -> List[Dict]:
    """지정 버전의 골든셋(`{version}_*.json`)만 로드한다.

    같은 폴더에 v1·v2 가 공존해도 버전이 섞이지 않도록 파일명 접두사로 스코프한다.
    """
    import glob
    import json

    golden: List[Dict] = []
    for path in sorted(glob.glob(f"{golden_dir}/{version}_*.json")):
        if path.endswith("_diagnostics.json") or path.endswith("_case_matrix.json"):
            continue
        with open(path, encoding="utf-8") as f:
            golden.extend(json.load(f))
    return golden


def _select_case_ids(golden: List[Dict], case_ids: set[str] | None) -> List[Dict]:
    """실험 case ID를 검증하고 요청된 순서가 아닌 골든 원래 순서를 유지합니다."""
    if case_ids is None:
        return golden
    known = {case["case_id"] for case in golden}
    unknown = case_ids - known
    if unknown:
        raise ValueError(f"골든셋에 없는 case_id가 있습니다: {sorted(unknown)}")
    selected = [case for case in golden if case["case_id"] in case_ids]
    if not selected:
        raise ValueError("case_ids에 해당하는 골든 케이스가 없습니다.")
    return selected


def _load_threshold_heldout_case_ids(version: str, golden_dir: str = GOLDEN_DIR) -> set[str] | None:
    """임계값 보정용 고정 held-out manifest가 있으면 case_id 집합을 읽습니다.

    골든 케이스 스키마를 확장하지 않고 `threshold_heldout.vN.json`에 분할을 별도 보관합니다.
    구버전 골든처럼 manifest가 없는 경우에는 None을 반환해 기존 전체합산 평가를 유지합니다.
    """
    import json

    path = Path(golden_dir) / f"threshold_heldout.{version}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    case_ids = payload.get("heldout_case_ids")
    if not isinstance(case_ids, list) or not all(isinstance(case_id, str) for case_id in case_ids):
        raise ValueError(f"임계값 held-out manifest 형식 오류: {path}")
    return set(case_ids)


def split_threshold_calibration_cases(
    golden: List[Dict],
    heldout_case_ids: set[str],
) -> Dict[str, List[Dict]]:
    """고정 manifest에 따라 골든을 tuning·heldout으로 나눕니다."""
    golden_case_ids = {case["case_id"] for case in golden}
    unknown_case_ids = heldout_case_ids - golden_case_ids
    if unknown_case_ids:
        raise ValueError(
            "임계값 held-out manifest에 현재 골든에 없는 case_id가 있습니다: "
            f"{sorted(unknown_case_ids)}"
        )
    heldout = [case for case in golden if case["case_id"] in heldout_case_ids]
    tuning = [case for case in golden if case["case_id"] not in heldout_case_ids]
    if not tuning or not heldout:
        raise ValueError("임계값 보정에는 tuning과 heldout 양쪽에 최소 1건이 필요합니다.")
    return {"tuning": tuning, "heldout": heldout}


def _group_cases_by_contract_type(golden: List[Dict]) -> Dict[str, List[Dict]]:
    """골든 케이스를 계약유형별 배치로 그룹화합니다."""
    by_type: Dict[str, List[Dict]] = {}
    for case in golden:
        by_type.setdefault(case["contract_type"], []).append(case)
    return by_type


def _detect_latest_version(golden_dir: str = GOLDEN_DIR) -> str:
    """golden_dir 의 `v<N>_*.json` 을 스캔해 가장 높은 v<N> 을 반환한다 (없으면 'v1')."""
    import glob
    import os
    import re

    versions = set()
    for path in glob.glob(f"{golden_dir}/v*_*.json"):
        m = re.match(r"v(\d+)_", os.path.basename(path))
        if m:
            versions.add(int(m.group(1)))
    return f"v{max(versions)}" if versions else "v1"


def _write_result_md(
    version: str,
    total_n: int,
    overall_ablation: Dict[str, Dict],
    by_type: Dict[str, Dict[str, Any]],
    k: int,
    golden_dir: str = GOLDEN_DIR,
    alerts: List[str] | None = None,
    deviation_sweep: List[Dict[str, float]] | None = None,
    toxic_sweep: List[Dict[str, float]] | None = None,
    calibration_sweeps: Dict[str, Dict[str, List[Dict[str, float]]]] | None = None,
) -> str:
    """버전 전체 평가 결과를 **단일** `{version}_result.md` 로 저장하고 경로를 반환한다.

    협업 루프의 산출물 — 팀원이 골든셋 버전 간 지표를 diff 로 비교할 수 있게 결정론적 포맷으로 쓴다.
    A-1(검색)은 유형 합산 한 표, A-2/A-3(분류)는 계약 유형별 한 표로 담는다.
    by_type: {contract_type: {"n","reviewed","dev","tox"}}
    """
    from datetime import datetime

    from config import app_env

    path = str(Path(golden_dir) / f"{version}_result.md")

    lines = [
        f"# {version} — 평가 결과",
        "",
        f"> 자동 생성: `src/eval/run_eval.py` · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"· `APP_ENV={app_env}` · 골든 `{version}_*.json` (전체 n={total_n}, 유형 {len(by_type)}종)",
        "> 지표는 결정론적이며 LLM-judge 를 쓰지 않는다 (AGENTS.md #5).",
        "",
        f"## A-1. 검색 ablation — 전체 합산 (Recall@{k} · MRR)",
        "",
        "> `hybrid_X_Y`와 `hybrid_rerank_X_Y`의 X:Y는 dense:BM25 RRF 가중치입니다. "
        "각 비율의 rerank 행은 동일 비율의 hybrid 후보 풀을 재정렬한 결과입니다.",
        "",
        f"| variant | recall@{k} | MRR | n |",
        "| --- | --- | --- | --- |",
    ]
    for variant in SEARCH_VARIANTS:
        r = overall_ablation[variant]
        lines.append(f"| {variant} | {r['recall@k']:.3f} | {r['mrr']:.3f} | {r['n']} |")

    lines += [
        "",
        "## A-2/A-3. 이탈·독소 분류 — 계약 유형별 (참음성 포함)",
        "",
        "| 유형 | n(검토됨) | 항목 | P | R | 특이도 | 정확도 | F1 | TP | FP | FN | TN |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for ct, m in by_type.items():
        head = f"{ct} | {m['n']}({m['reviewed']})"
        for label, s in (("이탈", m["dev"]), ("독소", m["tox"])):
            lines.append(
                f"| {head} | {label} | {s['precision']:.3f} | {s['recall']:.3f} | {s['specificity']:.3f} | "
                f"{s['accuracy']:.3f} | {s['f1']:.3f} | "
                f"{s['tp']:.0f} | {s['fp']:.0f} | {s['fn']:.0f} | {s['tn']:.0f} |"
            )
            head = " | "  # 같은 유형의 둘째 행은 유형·n 칸 비움

    def _append_threshold_table(title: str, threshold_name: str, sweep: List[Dict[str, float]]) -> None:
        lines.extend([
            "",
            title,
            "",
            "> 이 표는 후보 임계값 비교용입니다. 동일 골든셋에서 가장 높은 값을 자동 채택하지 말고, "
            "별도 held-out 검증과 사람 사인오프 후에만 프로덕션 기본값을 변경합니다.",
            "",
            f"| {threshold_name} | P | R | 특이도 | 정확도 | F1 | TP | FP | FN | TN |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for scores in sweep:
            lines.append(
                f"| {scores['threshold']:.2f} | {scores['precision']:.3f} | {scores['recall']:.3f} | "
                f"{scores['specificity']:.3f} | {scores['accuracy']:.3f} | {scores['f1']:.3f} | "
                f"{scores['tp']:.0f} | {scores['fp']:.0f} | {scores['fn']:.0f} | {scores['tn']:.0f} |"
            )

    if deviation_sweep:
        _append_threshold_table(
            "## A-2. 이탈 match_threshold 스윕 — 전체 합산",
            "match_threshold",
            deviation_sweep,
        )
    if toxic_sweep:
        _append_threshold_table(
            "## A-3. 독소 toxic_threshold 스윕 — 전체 합산",
            "toxic_threshold",
            toxic_sweep,
        )
    if calibration_sweeps:
        for split_name, sweeps in calibration_sweeps.items():
            _append_threshold_table(
                f"## A-2. 이탈 match_threshold 스윕 — {split_name} 전체합산",
                "match_threshold",
                sweeps["deviation"],
            )
            _append_threshold_table(
                f"## A-3. 독소 toxic_threshold 스윕 — {split_name} 전체합산",
                "toxic_threshold",
                sweeps["toxic"],
            )
    if alerts:
        lines += ["", "## ⚠️ 축퇴 경보", ""]
        lines += [f"- {a}" for a in alerts]

    lines += [
        "",
        "> 해석 주의: `특이도=0`(TN=0)은 정상·무해 케이스를 전부 양성으로 찍는 축퇴를 뜻한다. "
        f"근본 원인·강약점·다음 버전 반영점은 `{version}_review.md` 참조.",
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _run_track_a(
    k: int = 5,
    version: str | None = None,
    *,
    case_ids: set[str] | None = None,
    write_output: bool = True,
    output_dir: str | None = None,
) -> Dict[str, Any]:
    """트랙 A를 실행합니다.

    ``case_ids``로 실험 split을 제한하고 ``write_output=False`` 또는 ``output_dir``로
    동결 골든 산출물을 덮어쓰지 않게 할 수 있습니다.
    """
    from eval.ablation import run_ablation

    version = version or _detect_latest_version()
    golden = _select_case_ids(_load_golden(version), case_ids)
    logger.info(f"=== [{version}] 골든셋 로드: {len(golden)}건 ===")

    by_type = _group_cases_by_contract_type(golden)

    combined: Dict[str, List[Dict]] = {v: [] for v in SEARCH_VARIANTS}
    metrics_by_type: Dict[str, Dict[str, Any]] = {}
    review_results_by_type: Dict[str, Dict[str, Any]] = {}
    standard_hits_by_type: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    toxic_hits_by_type: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    alerts: List[str] = []
    for contract_type, cases in by_type.items():
        cbv = build_cases_by_variant(cases, k, contract_type)
        for variant, c in cbv.items():
            combined[variant].extend(c)

        review_results, standard_hits, toxic_hits = review_golden_clauses_with_trace(cases, contract_type)
        review_results_by_type[contract_type] = review_results
        standard_hits_by_type[contract_type] = standard_hits
        toxic_hits_by_type[contract_type] = toxic_hits
        dev = deviation_scores(cases, review_results)
        tox = toxic_scores(cases, review_results)
        metrics_by_type[contract_type] = {
            "n": len(cases), "reviewed": len(review_results), "dev": dev, "tox": tox,
        }
        type_alerts = (
            degeneracy_alerts(dev, f"{contract_type} 이탈")
            + degeneracy_alerts(tox, f"{contract_type} 독소")
        )
        for a in type_alerts:
            logger.warning(f"    {a}")
        alerts.extend(type_alerts)

        logger.info(f"── [{contract_type}] n={len(cases)} (검토됨={len(review_results)}) ──")
        logger.info(
            f"    이탈 : P={dev['precision']:.3f} R={dev['recall']:.3f} "
            f"특이도={dev['specificity']:.3f} 정확도={dev['accuracy']:.3f} F1={dev['f1']:.3f} "
            f"(TP={dev['tp']:.0f} FP={dev['fp']:.0f} FN={dev['fn']:.0f} TN={dev['tn']:.0f})"
        )
        logger.info(
            f"    독소 : P={tox['precision']:.3f} R={tox['recall']:.3f} "
            f"특이도={tox['specificity']:.3f} 정확도={tox['accuracy']:.3f} F1={tox['f1']:.3f} "
            f"(TP={tox['tp']:.0f} FP={tox['fp']:.0f} FN={tox['fn']:.0f} TN={tox['tn']:.0f})"
        )

    # 전체 합산 검색 ablation (유형 무관 대표 수치)
    overall = run_ablation(combined, k=k)
    logger.info(f"── [{version}] 전체 합산 A-1 (Recall@{k} · MRR) ──")
    for variant in SEARCH_VARIANTS:
        r = overall[variant]
        logger.info(f"    {variant:15s} recall@{k}={r['recall@k']:.3f}  mrr={r['mrr']:.3f}  n={r['n']}")

    deviation_sweep = deviation_threshold_sweep(by_type, review_results_by_type)
    toxic_sweep = toxic_threshold_sweep(by_type, toxic_hits_by_type)
    from eval.diagnostics import build_case_diagnostics, write_case_diagnostics
    diagnostics = build_case_diagnostics(
        by_type, review_results_by_type, toxic_hits_by_type, standard_hits_by_type,
        match_threshold=DEFAULT_MATCH_THRESHOLD, toxic_threshold=DEFAULT_TOXIC_THRESHOLD,
    )
    destination = output_dir or GOLDEN_DIR
    diagnostic_paths = None
    if write_output:
        Path(destination).mkdir(parents=True, exist_ok=True)
        diagnostic_paths = write_case_diagnostics(version, diagnostics, destination)
        logger.info(f"=== 진단 저장: {diagnostic_paths['json']}, {diagnostic_paths['markdown']} ===")
    calibration_sweeps = None
    heldout_case_ids = None if case_ids is not None else _load_threshold_heldout_case_ids(version)
    if heldout_case_ids is not None:
        calibration_sweeps = {}
        for split_name, split_cases in split_threshold_calibration_cases(golden, heldout_case_ids).items():
            split_by_type = _group_cases_by_contract_type(split_cases)
            split_review_results_by_type = {
                contract_type: {
                    case["case_id"]: review_results_by_type[contract_type][case["case_id"]]
                    for case in cases
                }
                for contract_type, cases in split_by_type.items()
            }
            split_toxic_hits_by_type = {
                contract_type: {
                    case["case_id"]: toxic_hits_by_type[contract_type][case["case_id"]]
                    for case in cases
                }
                for contract_type, cases in split_by_type.items()
            }
            calibration_sweeps[split_name] = {
                "deviation": deviation_threshold_sweep(split_by_type, split_review_results_by_type),
                "toxic": toxic_threshold_sweep(split_by_type, split_toxic_hits_by_type),
            }
    logger.info(
        "── 임계값 스윕 완료: "
        f"match={list(MATCH_THRESHOLD_SWEEP)}, toxic={list(TOXIC_THRESHOLD_SWEEP)}"
    )

    out = None
    if write_output:
        Path(destination).mkdir(parents=True, exist_ok=True)
        out = _write_result_md(
            version, len(golden), overall, metrics_by_type, k,
            golden_dir=destination, alerts=alerts,
            deviation_sweep=deviation_sweep, toxic_sweep=toxic_sweep,
            calibration_sweeps=calibration_sweeps,
        )
        logger.info(f"=== 결과 저장: {out} ===")
    return {
        "version": version, "n": len(golden), "metrics_by_type": metrics_by_type,
        "diagnostics": diagnostics, "result_md": out, "diagnostic_paths": diagnostic_paths,
    }


def _git_commit() -> str:
    """현재 코드 식별자를 반환합니다."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _toxic_summary(report: Dict[str, Any]) -> Dict[str, float]:
    """트랙 A 유형별 독소 결과를 실험용 전체 혼동행렬로 합칩니다."""
    counts = {key: 0 for key in ("tp", "fp", "fn", "tn")}
    for metrics_by_type in report["metrics_by_type"].values():
        for key in counts:
            counts[key] += metrics_by_type["tox"][key]
    return build_confusion_summary([
        {"outcome": outcome}
        for outcome, count in (
            ("TP", counts["tp"]), ("FP", counts["fp"]),
            ("FN", counts["fn"]), ("TN", counts["tn"]),
        )
        for _ in range(int(count))
    ])


def _write_experiment_json(path: Path, payload: Dict[str, Any]) -> str:
    """실험 전용 JSON 산출물을 결정론적 JSON으로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def _write_experiment_report(path: Path, payload: Dict[str, Any]) -> str:
    """before/after 혼동행렬과 사례 후보 diff를 포함한 실험 보고서를 저장합니다."""
    after = payload["after"]
    experiment_id = payload.get("experiment_id", EXPERIMENT_ID)
    candidate_diff = payload.get("candidate_diff", payload.get("toxic_top3_diff", []))
    lines = [
        f"# 실험 {experiment_id} — {payload['split']}", "",
        f"- 판정: **{payload['decision']}**", "- 입력 케이스: " + str(payload["case_count"]), "",
        "| 구분 | TP | FP | FN | TN | F1 |", "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| 기준선 | {payload['before']['tp']} | {payload['before']['fp']} | {payload['before']['fn']} | {payload['before']['tn']} | {payload['before']['f1']:.3f} |",
        f"| 후보 | {after['tp']} | {after['fp']} | {after['fn']} | {after['tn']} | {after['f1']:.3f} |", "",
        "## 후보 top-3 / 점수 diff", "",
        f"변경 사례 수: {len(candidate_diff)}", "",
    ]
    for row in candidate_diff:
        lines.append(f"- `{row['case_id']}`: 후보 top-3 변경")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _run_experiment_s(
    split: str, *, env: str | None = None, approval_file: str | None = None,
    write_output: bool = True, command: list[str] | None = None,
) -> Dict[str, Any]:
    """실험 S를 tuning 또는 승인된 held-out으로 실행합니다."""
    if split not in {"tuning", "held-out"}:
        raise ValueError("실험 S split은 tuning 또는 held-out이어야 합니다.")
    manifest = load_manifest(EXPERIMENT_S_MANIFEST)
    golden = _load_golden(EXPERIMENT_VERSION)
    partitions = split_cases(golden, manifest)
    selected = partitions[split]
    output_dir = EXPERIMENT_S_DIR
    tuning_path = output_dir / "tuning-result.json"
    record_path = output_dir / "heldout-run.json"
    if split == "held-out":
        if not write_output:
            raise ValueError("held-out에서는 --no-write를 사용할 수 없습니다.")
        if not approval_file:
            raise ValueError("held-out에는 --approval-file이 필요합니다.")
        if not tuning_path.exists():
            raise ValueError("tuning 결과 파일이 없습니다.")
        approval = json.loads(Path(approval_file).read_text(encoding="utf-8"))
        validate_run_record_absent(record_path)
        validate_approval_repository_state(approval_file)
        validate_approval(
            approval, manifest_sha256=sha256_file(EXPERIMENT_S_MANIFEST),
            tuning_report_sha256=sha256_file(tuning_path), code_commit=_git_commit(),
            expected_baseline_commit=BASELINE_COMMIT,
        )
        tuning_payload = json.loads(tuning_path.read_text(encoding="utf-8"))
        if not tuning_payload.get("passed"):
            raise ValueError("tuning 통과 결과가 없어 held-out을 실행할 수 없습니다.")

    reservation = {
        "experiment_id": EXPERIMENT_ID, "version": EXPERIMENT_VERSION,
        "split": split, "status": "STARTED",
        "input_manifest_sha256": sha256_file(EXPERIMENT_S_MANIFEST),
        "command": command or sys.argv,
        "environment": {"APP_ENV": os.getenv("APP_ENV", "local")},
    }
    if split == "held-out":
        # 평가 호출보다 먼저 선점한다. 두 프로세스 중 하나만 이 지점을 통과할 수 있다.
        reserve_run_record(record_path, reservation)
    try:
        result = _run_track_a(
            k=5, version=EXPERIMENT_VERSION,
            case_ids={case["case_id"] for case in selected},
            write_output=write_output, output_dir=str(output_dir),
        )
    except Exception as exc:
        if split == "held-out":
            update_run_record(record_path, {
                "status": "FAILED", "error": f"{type(exc).__name__}: {exc}",
            })
        raise
    after = _toxic_summary(result)
    before = (
        {"tp": 9, "fp": 5, "fn": 9, "tn": 13, "precision": 0.643, "recall": 0.5, "f1": 0.563}
        if split == "tuning" else
        {"tp": 2, "fp": 0, "fn": 7, "tn": 9, "precision": 1.0, "recall": 2 / 9, "f1": 0.364}
    )
    baseline_path = Path(GOLDEN_DIR) / "v4_diagnostics.json"
    baseline_rows: list[dict[str, Any]] = []
    if baseline_path.exists():
        baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        selected_ids = {case["case_id"] for case in selected}
        baseline_rows = [
            row for row in baseline_payload.get("toxic", [])
            if row.get("case_id") in selected_ids
        ]
    payload: Dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID, "version": EXPERIMENT_VERSION, "split": split,
        "case_count": len(selected), "manifest_sha256": sha256_file(EXPERIMENT_S_MANIFEST),
        "before": before, "after": after,
        "passed": tuning_passed(after) if split == "tuning" else heldout_passed(after),
        "decision": "통과" if (tuning_passed(after) if split == "tuning" else heldout_passed(after)) else "보류",
        "toxic_top3_diff": build_top3_diff(baseline_rows, result["diagnostics"].get("toxic", [])),
    }
    result_path = output_dir / ("tuning-result.json" if split == "tuning" else "heldout-result.json")
    _write_experiment_json(result_path, payload)
    _write_experiment_report(output_dir / ("tuning-result.md" if split == "tuning" else "heldout-result.md"), payload)
    if split == "held-out":
        from datetime import datetime, timezone
        update_run_record(record_path, {
            "status": "SUCCEEDED", "result_sha256": sha256_file(result_path),
            "confusion_matrix": after, "decision": payload["decision"],
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
    return payload


EXPERIMENT_C_DIR = Path("docs/experiments/C")


def _deviation_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    """case-level 이탈 진단 행을 실험용 혼동행렬로 집계합니다."""
    return build_confusion_summary(rows)


def _run_experiment_c(
    split: str, *, approval_file: str | None = None, write_output: bool = True,
    command: list[str] | None = None,
) -> Dict[str, Any]:
    """v5 SW OVER_MATCH 실험 C를 tuning 또는 승인된 held-out으로 실행합니다."""
    if split not in {"tuning", "held-out"}:
        raise ValueError("실험 C split은 tuning 또는 held-out이어야 합니다.")
    validate_baseline_inputs(EXPERIMENT_C_BASELINE)
    manifest = load_manifest(EXPERIMENT_C_MANIFEST)
    golden = [case for case in _load_golden("v5") if case.get("contract_type") == EXPERIMENT_C.contract_type]
    partitions = split_sw_cases(golden, manifest)
    selected = partitions[split]
    output_dir = EXPERIMENT_C_DIR
    tuning_path, record_path = output_dir / "tuning-result.json", output_dir / "heldout-run.json"
    if split == "held-out":
        if not write_output or not approval_file:
            raise ValueError("C held-out에는 쓰기 모드와 --approval-file이 필요합니다.")
        if not tuning_path.exists():
            raise ValueError("C tuning 결과 파일이 없습니다.")
        approval = json.loads(Path(approval_file).read_text(encoding="utf-8"))
        validate_run_record_absent(record_path)
        validate_generic_approval_repository_state(approval_file, repo_root=".", baseline_commit=EXPERIMENT_C.baseline_commit)
        validate_c_approval(
            approval, manifest_sha256=sha256_file(EXPERIMENT_C_MANIFEST),
            tuning_report_sha256=sha256_file(tuning_path), code_commit=_git_commit(),
        )
        if not json.loads(tuning_path.read_text(encoding="utf-8")).get("passed"):
            raise ValueError("C tuning 통과 결과가 없어 held-out을 실행할 수 없습니다.")
    reservation = {
        "experiment_id": "C", "version": "v5", "split": split, "status": "STARTED",
        "input_manifest_sha256": sha256_file(EXPERIMENT_C_MANIFEST), "case_matrix_sha256": sha256_file(EXPERIMENT_C_CASE_MATRIX),
        "command": command or sys.argv, "environment": {"APP_ENV": os.getenv("APP_ENV", "local")},
    }
    if split == "held-out":
        reserve_run_record(record_path, reservation)
    try:
        result = _run_track_a(k=5, version="v5", case_ids={case["case_id"] for case in selected}, write_output=write_output, output_dir=str(output_dir))
    except Exception as exc:
        if split == "held-out":
            update_run_record(record_path, {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        raise
    after_rows = [row for row in result["diagnostics"].get("deviation", []) if row.get("contract_type") == "SW_FREELANCE"]
    before_payload = json.loads(EXPERIMENT_C_BASELINE_DIAGNOSTICS.read_text(encoding="utf-8"))
    selected_ids = {case["case_id"] for case in selected}
    before_rows = [row for row in before_payload["deviation"] if row.get("case_id") in selected_ids]
    before, after = _deviation_summary(before_rows), _deviation_summary(after_rows)
    passed_result = passed(after, EXPERIMENT_C, split)
    payload: Dict[str, Any] = {
        "experiment_id": "C", "version": "v5", "split": split, "case_count": len(selected),
        "manifest_sha256": sha256_file(EXPERIMENT_C_MANIFEST), "case_matrix_sha256": sha256_file(EXPERIMENT_C_CASE_MATRIX),
        "before": before, "after": after, "passed": passed_result,
        "decision": "통과" if passed_result else ("폐기" if split == "tuning" else "보류"),
        "overmatch_taxonomy": classify_overmatch(before_rows, json.loads(EXPERIMENT_C_CASE_MATRIX.read_text(encoding="utf-8"))) if split == "tuning" else [],
        "candidate_diff": build_top3_diff(before_rows, after_rows),
    }
    result_path = output_dir / ("tuning-result.json" if split == "tuning" else "heldout-result.json")
    _write_experiment_json(result_path, payload)
    _write_experiment_report(output_dir / ("tuning-result.md" if split == "tuning" else "heldout-result.md"), payload)
    if split == "tuning":
        write_taxonomy(output_dir / "C_overmatch_taxonomy.md", payload["overmatch_taxonomy"])
    else:
        update_run_record(record_path, {"status": "SUCCEEDED", "result_sha256": sha256_file(result_path), "confusion_matrix": after, "decision": payload["decision"]})
    return payload


# ─────────────────────────────────────────────────────────────────────────
# Track B (실계약 문서 단위) — M:N 커버리지 + 강건성. 상세 규격: docs/tasks/D_eval.md §트랙 B
# 라벨 없이: raw/ 의 각 실계약 문서를 coverage_types(SW·SI·SM) 각 표준코퍼스와 M:N 으로 대조해
# 표준 커버리지·NO_MATCH·deviation 분포를 셀마다 계산한다(문서는 유형별 재파싱 없이 1회 파싱·재사용).
# 절대값은 정답이 아니라 'vN(=시스템 버전) 비교 신호'다 — 검증된 MISSING Recall 은 스코프에서 제외.
# ─────────────────────────────────────────────────────────────────────────

GOLDEN_B_DIR = "src/eval/golden_b"


def _coverage_types_default() -> List[Any]:
    """M:N 커버리지에서 대조할 표준 유형 집합(기본: 전체 3종). main 에서 주입해 축소 가능."""
    from contracts.enums import ContractType

    return [
        ContractType.SW_FREELANCE,
        ContractType.SI_SUBCONTRACT,
        ContractType.SM_SUBCONTRACT,
    ]


def _discover_raw_docs(golden_b_dir: str = GOLDEN_B_DIR) -> List[str]:
    """`raw/` 의 실계약 원본을 모두 찾아 golden_b 기준 상대경로(`raw/<name>`)로 반환한다.

    라벨 파일이 아니라 **파일 자체가 평가 대상**이다(유형은 코드의 coverage_types 로 지정).
    `.gitkeep`·숨김파일은 제외.
    """
    import glob
    import os

    docs: List[str] = []
    for path in sorted(glob.glob(f"{golden_b_dir}/raw/*")):
        name = os.path.basename(path)
        if name.startswith(".") or not os.path.isfile(path):
            continue
        docs.append(f"raw/{name}")
    return docs


def _next_version_b(golden_b_dir: str = GOLDEN_B_DIR) -> str:
    """트랙 B 실행 버전을 자동 증가시킨다. 기존 `v<N>_b_result.md` 중 최댓값+1 (없으면 'v1').

    트랙 B 의 vN 은 리랭커 모델·튜닝·임계값 등 '시스템/런 버전'이다. 그냥 돌리면 새 버전이
    생기고, 특정 버전을 덮어쓰려면 인자로 명시한다(`run_eval b v2`). 라벨은 스캔하지 않는다
    (라벨엔 vN 이 없으므로 — 트랙 A 의 `_detect_latest_version` 과 다른 이유).
    """
    import glob
    import os
    import re

    versions = set()
    for path in glob.glob(f"{golden_b_dir}/v*_b_result.md"):
        m = re.match(r"v(\d+)_b_result\.md$", os.path.basename(path))
        if m:
            versions.add(int(m.group(1)))
    return f"v{max(versions) + 1}" if versions else "v1"


def _parse_document_b(doc_path: str, golden_b_dir: str = GOLDEN_B_DIR) -> List[Any]:
    """실계약 문서 1건을 KordocParser 로 파싱해 조항 목록을 반환한다(유형 무관, 문서당 1회).

    server.py 와 동일하게 원본(HWP/PDF/…)을 직접 파싱한다(지름길 없음 — 실전 파싱 강건성 검증).
    M:N 대조에서 같은 문서를 유형 수만큼 재파싱하지 않도록, 파싱 결과를 여러 유형에 재사용한다.
    """
    from contracts.implement import KordocParser

    resolved = doc_path if Path(doc_path).is_absolute() else str(Path(golden_b_dir) / doc_path)
    return KordocParser().parse(resolved)


def review_document_against_type(clauses: List[Any], ct: Any) -> tuple[List[Any], int]:
    """이미 파싱된 조항을 특정 유형 표준코퍼스와 대조한다(review_contract 전체 파이프).

    반환: (검토결과 목록, 그 유형 표준조항 수). 법령 근거·독소는 커버리지 지표와 무관하므로
    NullGrounder + use_toxic=False 로 생략(네트워크·불필요 계산 차단).
    """
    from pipe.review_pipe import review_contract
    from adapter import vector, reranker, embedder

    standards = _load_standards(ct.value)
    results = review_contract(
        clauses, ct,
        retriever=vector, embedder=embedder, reranker=reranker, grounder=NullGrounder(),
        all_standard_clauses=standards, use_toxic=False,
    )
    return results, len(standards)


def _coverage_cell(results: List[Any], n_standards: int) -> Dict[str, Any]:
    """(문서 × 유형) 한 셀 지표: 표준 커버리지·NO_MATCH·deviation 분포.

    coverage = 매칭된 표준 수 / 전체 표준 수 = (n_standards − MISSING) / n_standards.
    라벨이 없으므로 MISSING 이 '진짜 누락'인지 '매칭 실패'인지는 구분하지 않는다 —
    절대값이 아니라 유형 간·버전 간 **비교 신호**로 읽는다. 자기 유형에서 coverage 가 높고
    NO_MATCH 가 낮게 나오는 것이 정상 기대(단, 유형 간 조항 겹침으로 분리가 흐릴 수 있음).
    """
    from contracts.enums import Deviation

    clause_results = [r for r in results if r.user_clause]  # 사용자 조항 판정 (MISSING 은 user_clause="")
    missing = sum(1 for r in results if r.deviation == Deviation.MISSING)
    dist: Dict[str, int] = {}
    for r in clause_results:
        dist[r.deviation.value] = dist.get(r.deviation.value, 0) + 1
    matched_std = max(n_standards - missing, 0)
    return {
        "n_clauses": len(clause_results),
        "n_standards": n_standards,
        "matched_std": matched_std,
        "missing": missing,
        "coverage": matched_std / n_standards if n_standards else 0.0,
        "no_match": dist.get(Deviation.NO_MATCH.value, 0),
        "deviation_dist": dist,
    }


def _dump_coverage_doc(row: Dict[str, Any]) -> None:
    """사람 확인용 덤프(강건성 스팟체크)를 stdout 으로 출력한다: 파싱 결과 + 유형별 커버리지 셀."""
    print(f"\n{'=' * 84}\n[{row['doc']}]  파싱 조항수={row['n_parsed']}  best-fit={row['best_fit']}\n{'=' * 84}")
    for ct_value, c in row["cells"].items():
        print(
            f"  {ct_value:16} cov={c['coverage']:.2f} (표준 {c['matched_std']}/{c['n_standards']}, "
            f"MISSING={c['missing']})  NO_MATCH={c['no_match']}  분포={c['deviation_dist']}"
        )


def _write_coverage_b_md(
    version: str, matrix: List[Dict], coverage_types: List[Any], golden_b_dir: str = GOLDEN_B_DIR
) -> str:
    """Track B 결과를 `{version}_b_result.md` 로 저장(M:N 커버리지 매트릭스 + 강건성 섹션)."""
    from datetime import datetime

    from config import app_env

    type_values = [ct.value for ct in coverage_types]
    path = str(Path(golden_b_dir) / f"{version}_b_result.md")
    lines = [
        f"# {version} · Track B (실계약) — M:N 커버리지 평가",
        "",
        f"> 자동 생성: `eval.run_eval.evaluate_coverage_b` · "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · `APP_ENV={app_env}` · "
        f"문서 {len(matrix)}건 × 유형 {len(coverage_types)}종",
        "> ⚠️ 라벨 없는 자동 지표 — **절대값은 정답이 아니라 vN(=시스템 버전) 비교 신호**다. "
        "유형 간 조항 겹침으로 커버리지가 비슷할 수 있으니 델타(vN 간)로 해석하고 최적화 목표로 삼지 말 것.",
        "> `coverage = (전체 표준 − MISSING) / 전체 표준`. best-fit = 커버리지 최대 유형.",
        "",
        "## 커버리지 매트릭스 (문서 × 유형 — 셀: `coverage (NM=NO_MATCH)`)",
        "",
        "| 문서 | 조항수 | " + " | ".join(type_values) + " | best-fit |",
        "| --- | --- | " + " | ".join(["---"] * len(type_values)) + " | --- |",
    ]
    for row in matrix:
        if row.get("parse_error"):
            cells_md = " | ".join(["파싱실패"] * len(type_values))
            lines.append(f"| {row['doc']} | 0 | {cells_md} | — |")
            continue
        cells_md = " | ".join(
            f"{row['cells'][tv]['coverage']:.2f} (NM={row['cells'][tv]['no_match']})" for tv in type_values
        )
        lines.append(f"| {row['doc']} | {row['n_parsed']} | {cells_md} | {row['best_fit']} |")

    lines += ["", "## 문서별 상세 (best-fit 유형 기준 deviation 분포)", ""]
    for row in matrix:
        if row.get("parse_error"):
            lines.append(f"- **{row['doc']}** — ⚠️ 파싱 실패: `{row['parse_error']}`")
            continue
        best = row["best_fit"]
        c = row["cells"][best]
        degeneracy = coverage_degeneracy_alert(c["deviation_dist"])
        lines.append(
            f"- **{row['doc']}** (best-fit `{best}`): 조항 {c['n_clauses']} · "
            f"coverage {c['coverage']:.2f} (표준 {c['matched_std']}/{c['n_standards']}) · "
            f"NO_MATCH {c['no_match']} · 분포 {c['deviation_dist']}"
            + (f" · {degeneracy}" if degeneracy else "")
        )

    lines += [
        "",
        "## 강건성 스팟체크 (사람 작성 — 정성, 지표 없음)",
        "",
        "> `run_eval b` 실행 시 함께 출력되는 문서 덤프를 훑고 아래를 채운다.",
        "",
        "- 파싱 성공/실패 · 깨진 조항 여부 — ",
        "- best-fit 이 상식과 맞는가(프리랜서 문서가 SW_FREELANCE 로?) · 유형 간 분리가 뚜렷한가 — ",
        "- NO_MATCH 폭주·비정상 deviation 분포 여부 — ",
        "- 기타 — ",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def evaluate_coverage_b(
    version: str | None = None, coverage_types: List[Any] | None = None,
    golden_b_dir: str = GOLDEN_B_DIR, write_md: bool = True, verbose_dump: bool = False,
) -> Dict[str, Any]:
    """Track B 자동 지표: raw/ 의 각 문서 × coverage_types 각 표준코퍼스의 M:N 커버리지.

    라벨·`expected_missing` 없이 표준 커버리지·NO_MATCH·deviation 분포를 셀마다 계산한다.
    절대값은 정답이 아니라 **버전(vN=시스템) 비교 신호**다(문서 2~3건·유형 겹침 → 델타로 해석).
    문서는 유형별로 재파싱하지 않도록 1회 파싱해 재사용한다. verbose_dump=True 면 유형별 셀을
    stdout 으로도 출력(강건성 스팟체크용).
    """
    version = version or _next_version_b(golden_b_dir)
    coverage_types = coverage_types or _coverage_types_default()
    docs = _discover_raw_docs(golden_b_dir)
    logger.info(
        f"=== [Track B · {version}] raw 문서 {len(docs)}건 × 유형 {len(coverage_types)}종 M:N 커버리지 ==="
    )
    if not docs:
        logger.info(f"raw 문서가 없습니다. {golden_b_dir}/raw/ 에 실계약 파일을 넣으세요.")
        return {"version": version, "matrix": [], "result_md": None}

    matrix: List[Dict[str, Any]] = []
    for doc in docs:
        try:
            clauses = _parse_document_b(doc, golden_b_dir)  # 유형 무관 1회 파싱
        except Exception as e:  # 파싱 실패도 트랙 B 가 잡으려는 신호 — 조용히 죽지 않고 기록
            logger.warning(f"  [{doc}] 파싱 실패: {e}")
            matrix.append({"doc": doc, "parse_error": str(e), "cells": {}})
            continue
        if not clauses:
            logger.warning(f"  [{doc}] 파싱 결과 조항 0건 (kordoc 미지원 포맷 가능성)")
            matrix.append({"doc": doc, "parse_error": "조항 0건", "cells": {}})
            continue

        cells: Dict[str, Any] = {}
        for ct in coverage_types:
            results, n_std = review_document_against_type(clauses, ct)
            cells[ct.value] = _coverage_cell(results, n_std)
        best_fit = max(cells, key=lambda t: cells[t]["coverage"])
        row = {"doc": doc, "n_parsed": len(clauses), "cells": cells, "best_fit": best_fit}
        matrix.append(row)
        if verbose_dump:
            _dump_coverage_doc(row)
        cov_str = "  ".join(f"{t}={cells[t]['coverage']:.2f}" for t in cells)
        logger.info(f"  [{doc}] 조항={len(clauses)} best-fit={best_fit} | {cov_str}")

    out = _write_coverage_b_md(version, matrix, coverage_types, golden_b_dir) if write_md else None
    if out:
        logger.info(f"=== 결과 저장: {out} ===")
    return {"version": version, "matrix": matrix, "result_md": out}


def _run_track_b(version: str | None = None, coverage_types: List[Any] | None = None) -> None:
    """트랙 B (실계약 문서 단위): raw/ 각 문서 × coverage_types 표준코퍼스 M:N 커버리지.

    라벨 없이 표준 커버리지·NO_MATCH·deviation 분포를 셀마다 계산·덤프하고 `{version}_b_result.md`
    로 저장한다. 문서는 유형별 재파싱 없이 1회 파싱·재사용한다. version 생략 시 `_next_version_b`
    로 자동 증가(기존 `vN_b_result.md` 최댓값+1). 특정 버전 덮어쓰기는 인자로 명시(`run_eval b v2`).
    """
    evaluate_coverage_b(version, coverage_types, write_md=True, verbose_dump=True)



class _TracingReranker:
    """eval에서 실제 review 호출의 표준·서브청크·독소 후보를 보존하는 프록시."""

    def __init__(self, delegate: Any):
        self._delegate = delegate
        self.standard_hits: List[List[Dict[str, Any]]] | None = None
        self.sub_chunk_hits: List[List[Dict[str, Any]]] | None = None
        self.toxic_hits: List[List[Dict[str, Any]]] | None = None

    def rerank_many(self, queries: List[str], hits_per_query: List[List[Dict[str, Any]]], text_key: str, top_k: int) -> List[List[Dict[str, Any]]]:
        reranked = self._delegate.rerank_many(queries, hits_per_query, text_key=text_key, top_k=top_k)
        sample = next((hit for hits in hits_per_query for hit in hits), None)
        if sample is None:
            return reranked
        if "pattern" in sample:
            self.toxic_hits = reranked
            return reranked
        if "parent_clause_id" in sample:
            self.sub_chunk_hits = reranked
        else:
            self.standard_hits = reranked
        return reranked

    def candidates_by_case(self, golden: List[Dict]) -> Dict[str, List[Dict[str, Any]]]:
        standard_batch = self.standard_hits or [[] for _ in golden]
        sub_chunk_batch = self.sub_chunk_hits or [[] for _ in golden]
        by_case: Dict[str, List[Dict[str, Any]]] = {}
        for case, standard_hits, sub_chunk_hits in zip(golden, standard_batch, sub_chunk_batch):
            candidates = [
                *({**hit, "source": STANDARD_COLLECTION} for hit in standard_hits),
                *({**hit, "source": SUB_CHUNK_COLLECTION} for hit in sub_chunk_hits),
            ]
            candidates.sort(key=lambda hit: (-float(hit.get("rerank_score", 0.0)), str(hit.get("id", ""))))
            by_case[case["case_id"]] = candidates[:3]
        return by_case

    def toxic_candidates_by_case(self, golden: List[Dict]) -> Dict[str, List[Dict[str, Any]]]:
        """동일 review 실행에서 재정렬된 독소 top-3를 case별로 반환합니다."""
        toxic_batch = self.toxic_hits or [[] for _ in golden]
        return {
            case["case_id"]: [
                {**hit, "source": "toxic_patterns"}
                for hit in hits[:3]
            ]
            for case, hits in zip(golden, toxic_batch)
        }


def review_golden_clauses_with_trace(
    golden: List[Dict], contract_type: str,
) -> tuple[
    Dict[str, Any],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
]:
    """한 번의 실제 review 실행에서 결과와 표준·독소 후보 trace를 함께 얻습니다."""
    from adapter import vector, reranker, embedder
    from contracts.enums import ContractType
    from contracts.models import Clause
    from pipe.review_pipe import review_contract

    ct = ContractType(contract_type)
    standards = _load_standards(contract_type)
    clauses = [Clause(idx=i + 1, num="", title="", text=g["user_clause"]) for i, g in enumerate(golden)]
    tracing_reranker = _TracingReranker(reranker)
    review_results = review_contract(
        clauses, ct,
        retriever=vector,
        embedder=embedder,
        reranker=tracing_reranker,
        grounder=NullGrounder(),
        all_standard_clauses=standards,
    )
    by_text = {result.user_clause: result for result in review_results if result.user_clause}
    by_case = {
        case["case_id"]: by_text[case["user_clause"]]
        for case in golden
        if case["user_clause"] in by_text
    }
    return (
        by_case,
        tracing_reranker.candidates_by_case(golden),
        tracing_reranker.toxic_candidates_by_case(golden),
    )
def main(
    track: str = "a", version: str | None = None, k: int = 5,
    coverage_types: List[Any] | None = None,
    *, case_ids: set[str] | None = None,
    write_output: bool = True,
    output_dir: str | None = None,
    experiment: str | None = None,
    split: str | None = None,
    approval_file: str | None = None,
) -> Dict[str, Any] | None:
    """평가 드라이버 진입점. track 인자로 트랙을 분기한다(기본 'a').

    - track='a': 합성 조항 단위(검색·이탈·독소). `{version}_result.md` 생성.
    - track='b': 실계약 문서 단위(M:N 커버리지·강건성). `{version}_b_result.md` 생성.
      coverage_types 로 대조할 표준 유형 집합을 지정한다(None → 전체 3종 SW·SI·SM).
    """
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
    _install_eval_embedding_cache()  # 실험 S도 실제 review 경로와 동일한 드라이버 준비를 사용
    if experiment is not None:
        if split is None or experiment not in {EXPERIMENT_ID, "C"}:
            raise ValueError("지원되는 실험은 --experiment=S|C와 --split=tuning|held-out 조합입니다.")
        if experiment == "C":
            manifest = load_manifest(EXPERIMENT_C_MANIFEST)
            ensure_case_ids_allowed(case_ids, heldout_ids=set(manifest["heldout_case_ids"]), split=split)
            return _run_experiment_c(split, approval_file=approval_file, write_output=write_output, command=sys.argv)
        manifest = load_manifest(EXPERIMENT_S_MANIFEST)
        ensure_case_ids_allowed(case_ids, heldout_ids=set(manifest["heldout_case_ids"]), split=split)
        return _run_experiment_s(split, approval_file=approval_file, write_output=write_output, command=sys.argv)
    if split is not None or approval_file is not None:
        raise ValueError("--split/--approval-file은 실험 S에서만 사용할 수 있습니다.")
    if track == "a" and (version or "").lower() == EXPERIMENT_VERSION and case_ids is not None:
        # 실험 플래그를 빼먹은 일반 CLI도 v4 held-out을 case ID로 열 수 없게 한다.
        manifest = load_manifest(EXPERIMENT_S_MANIFEST)
        ensure_case_ids_allowed(case_ids, heldout_ids=set(manifest["heldout_case_ids"]), split=None)
    if track == "b":
        _run_track_b(version, coverage_types)
    else:
        return _run_track_a(
            k, version, case_ids=case_ids,
            write_output=write_output, output_dir=output_dir,
        )
    return None


def _parse_cli_args(argv: List[str]) -> Dict[str, Any]:
    """평가 격리 옵션을 포함한 간단한 CLI 인자를 결정론적으로 파싱합니다."""
    track = argv[0] if argv and not argv[0].startswith("--") else "a"
    version_index = 1 if track != "a" or (argv and not argv[0].startswith("--")) else 0
    version = argv[version_index] if len(argv) > version_index and not argv[version_index].startswith("--") else None
    case_ids: set[str] | None = None
    output_dir: str | None = None
    write_output = True
    experiment: str | None = None
    split: str | None = None
    approval_file: str | None = None
    for arg in argv:
        if arg.startswith("--case-ids="):
            case_ids = {value for value in arg.split("=", 1)[1].split(",") if value}
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
        elif arg == "--no-write":
            write_output = False
        elif arg.startswith("--experiment="):
            experiment = arg.split("=", 1)[1]
        elif arg.startswith("--split="):
            split = arg.split("=", 1)[1]
        elif arg.startswith("--approval-file="):
            approval_file = arg.split("=", 1)[1]
    parsed = {
        "track": track, "version": version, "case_ids": case_ids,
        "output_dir": output_dir, "write_output": write_output,
    }
    if experiment is not None or split is not None or approval_file is not None:
        parsed.update({"experiment": experiment, "split": split, "approval_file": approval_file})
    return parsed


if __name__ == "__main__":
    # 사용법: python -m eval.run_eval [a|b] [version]
    #   python -m eval.run_eval            # 트랙 A, 최신 버전
    #   python -m eval.run_eval b          # 트랙 B, 새 vN 자동 증가 (raw/ × SW·SI·SM M:N 커버리지)
    #   python -m eval.run_eval b v2       # 트랙 B, v2 로 덮어쓰기
    #   python -m eval.run_eval a v2       # 트랙 A, v2
    main(**_parse_cli_args(sys.argv[1:]))
