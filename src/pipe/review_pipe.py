"""
[담당: 팀원 C + 리드] review_contract — 계약서 전체 검토 조립 (MCP 본체)

개정 사항: 1차 판정을 매칭 임계값 단일 기준으로 전면 단순화하여 CHANGED 및 커버리지 2패스를 삭제.

규격(통과해야 할 테스트): tests/pipe/test_review_pipe.py
참고 문서: src/pipe/README.md, src/core/README.md, 기획서 4·7장

core 의 순수 함수를 조립하고, 외부 작업(검색·재정렬·법령·그래프)은 ports 로 주입받습니다.
⚠ 시그니처는 동결 MCP 계약(4장)에 가깝습니다 — 변경 시 PM/리드와 먼저 합의하세요.

흐름(기획서 7장):
  batch 검색(Retriever.search_many) → 재정렬(Reranker, 이미 0~1 정규화된 rerank_score 반환) → select_best_match
  → classify_clause_deviation → 독소(Toxic)·연관위험(Graph) 풍부화
"""
from typing import Any, Dict, List, Optional, Tuple, Callable
import logging

logger = logging.getLogger(__name__)

from contracts.enums import Category, ContractType, Deviation, ToxicPattern, ProgressPhase
from contracts.models import Clause, StandardClause, DeviationResult, GroundingLaw
from contracts.ports import Grounder, Graph
from adapter.port import Retriever, Reranker, Embedder
from core import (
    classify_clause_deviation,
    detect_missing_clauses,
    detect_toxic_patterns,
    prepare_toxic_rerank_candidates,
    roll_up_sub_chunks,
    select_best_match,
)
from core.splitter import normalize_for_search

# Chroma 컬렉션 이름 (build_index.py 와 일치)
STANDARD_COLLECTION = "standard_clauses"
SUB_CHUNK_COLLECTION = "standard_sub_chunks"
TOXIC_COLLECTION = "toxic_patterns"


def _normalized_score(hit: Dict[str, Any]) -> float:
    """재정렬을 거친 검색 결과의 rerank_score를 0~1 정규화 점수로 취급합니다.

    search()가 반환하는 fusion_score(RRF, 최댓값 ≈0.033)는 match_threshold(0.5)와 스케일이
    맞지 않으므로 매칭 판정에 쓰지 않습니다. 반드시 Reranker 를 통과한 rerank_score 만 사용합니다.
    BgeReranker(CrossEncoder, num_labels=1)는 predict() 내부에서 이미 Sigmoid를 적용해
    0~1 확률값을 반환하므로, 여기서 다시 sigmoid를 적용하면 안 됩니다(치역이 [0.5, 0.731)로
    압축돼 match_threshold=0.5가 사실상 무력화되는 실측 버그였음).
    """
    return float(hit["rerank_score"]) if "rerank_score" in hit else 0.0


def _standard_from_hit(
    hit: Dict[str, Any],
    standards_by_id: Dict[str, StandardClause],
    contract_type: ContractType,
) -> Optional[StandardClause]:
    """standard_clauses 검색 결과 dict를 StandardClause로 변환합니다."""
    clause_id = hit.get("id") or hit.get("clause_id")
    if not clause_id:
        return None
    if clause_id in standards_by_id:
        return standards_by_id[clause_id]

    # 메모리 코퍼스에 없으면(예: 인덱스와 코퍼스 버전 불일치) 메타데이터로 복원 시도
    if "category" not in hit:
        return None
    return StandardClause(
        clause_id=clause_id,
        contract_type=ContractType(hit.get("contract_type", contract_type.value)),
        category=Category(hit["category"]),
        title=hit.get("title", ""),
        text=hit.get("text", ""),
        source=hit.get("source", ""),
        version=hit.get("version", ""),
    )


def _clause_candidates(
    reranked_hits: List[Dict[str, Any]],
    standards_by_id: Dict[str, StandardClause],
    contract_type: ContractType,
) -> List[Tuple[StandardClause, float]]:
    """standard_clauses 재정렬 결과를 (StandardClause, 정규화 점수) 후보로 변환합니다."""
    candidates: List[Tuple[StandardClause, float]] = []
    for hit in reranked_hits:
        standard = _standard_from_hit(hit, standards_by_id, contract_type)
        if standard is not None:
            candidates.append((standard, _normalized_score(hit)))
    return candidates


def _sub_chunk_candidate(
    reranked_sub_hits: List[Dict[str, Any]],
    standards_by_id: Dict[str, StandardClause],
) -> Optional[Tuple[StandardClause, float]]:
    """서브청크 검색 결과를 parent_clause_id 기준으로 roll-up 해 부모 조항 후보 1개로 만듭니다.

    거대 조항(항·호가 많은 조항)은 조항 전체 임베딩보다 항 단위 서브청크가 더 잘 매칭됩니다.
    parent_clause_id 별 Max Score(core.roll_up_sub_chunks)로 최적 부모를 고른 뒤,
    현재 계약 유형의 표준조항 코퍼스에 존재하는 부모만 후보로 채택합니다.
    """
    scored_parents: List[Tuple[str, float]] = [
        (hit["parent_clause_id"], _normalized_score(hit))
        for hit in reranked_sub_hits
        if hit.get("parent_clause_id")
    ]
    parent_id, score = roll_up_sub_chunks(scored_parents)
    if parent_id is None or parent_id not in standards_by_id:
        return None
    return standards_by_id[parent_id], score


def _toxic_from_hits(
    reranked_toxic_hits: List[Dict[str, Any]],
    threshold: float,
) -> List[ToxicPattern]:
    """toxic_patterns 검색 결과를 (ToxicPattern, 점수)로 변환 후 임계 필터링합니다."""
    matches: List[Tuple[ToxicPattern, float]] = []
    for hit in reranked_toxic_hits:
        raw = hit.get("pattern")
        if raw is None:
            continue
        try:
            pattern = ToxicPattern(raw)
        except ValueError:
            continue  # 알 수 없는 패턴 값은 건너뜀
        matches.append((pattern, _normalized_score(hit)))
    return detect_toxic_patterns(matches, threshold)


def _grounding_for(
    grounder: Grounder,
    category: Category,
    contract_type: ContractType,
    cache: Dict[Tuple[Category, ContractType], Tuple[GroundingLaw, ...]],
) -> List[GroundingLaw]:
    """이탈(MISSING) 조항에 법령 근거를 부착합니다. GENERAL 은 grounding 대상 아님.

    contract_type을 함께 넘겨 SI/SM(하도급) 전용 법령 오버라이드가 적용되게 한다
    (O_grounding_contract_type.md).
    """
    if category == Category.GENERAL:
        return []
    key = (category, contract_type)
    cached = cache.get(key)
    if cached is None:
        # 예외는 캐시에 넣지 않아 다음 누락 조항에서 재시도할 수 있게 한다. 빈 목록은
        # 정확 법령명 불일치의 명시적 NO_RESULT이므로 정상 결과로 캐시한다.
        cached = tuple(grounder.get_grounding(category, contract_type))
        cache[key] = cached
    # DeviationResult 소비자가 목록/모델을 바꾸어도 동일 요청의 캐시가 오염되지 않는다.
    return [law.model_copy(deep=True) for law in cached]


def review_contract(
    clauses: List[Clause],
    contract_type: ContractType,
    *,
    retriever: Retriever,
    embedder: Embedder,
    reranker: Reranker,
    grounder: Grounder,
    all_standard_clauses: List[StandardClause],
    graph: Optional[Graph] = None,
    match_threshold: float = 0.5,
    toxic_threshold: float = 0.6,
    top_k: int = 5,
    toxic_top_k: int = 3,
    use_sub_chunk: bool = True,
    use_toxic: bool = True,
    progress_callback: Optional[Callable[[int, int, ProgressPhase], None]] = None,
) -> List[DeviationResult]:
    """
    사용자 조항들을 표준조항과 비교해 이탈을 탐지하고, 법령 근거·독소패턴·연관위험을 부착합니다.

    절차:
      1. 컬렉션별 배치 검색(search_many)
      2. 조항마다 reranker 재정렬(이미 0~1 정규화된 rerank_score) → select_best_match 로 매칭 확정
         (검색 후보가 아예 없으면 NO_MATCH, 후보는 있으나 임계 미달이면 EXTRA)
         매칭 성공 시 1차 결정론에 따라 Deviation.NONE(잠정)으로 이탈 분류 수행.
      3. use_toxic: toxic_patterns 역방향 검색 → detect_toxic_patterns 로 독소 패턴 부착
      4. MISSING 이탈에 grounder 로 법령 근거, graph 로 연관위험 조항 부착
      5. detect_missing_clauses 로 누락 표준조항 추가

    Args:
        retriever: 벡터 DB·BM25 하이브리드 검색 포트.
        embedder: 조항 텍스트를 밀도 벡터로 변환하는 포트.
        reranker: 크로스 인코더 재정렬 포트.
        grounder: 이탈 조항(MISSING)에 관련 법령 근거를 부착하는 포트.
        all_standard_clauses: 계약 유형에 해당하는 표준조항 전체 목록.
        graph: 연관위험 조항 탐색 포트.
        match_threshold: 대응 표준조항으로 인정할 최소 정규화 점수(0~1).
        toxic_threshold: 독소 패턴으로 인정할 최소 정규화 점수(0~1).
        top_k: 표준/서브청크 컬렉션 검색·재정렬 시 가져올 상위 후보 수.
        toxic_top_k: 독소 컬렉션 전용 후보 수.
        use_sub_chunk: True 이면 standard_sub_chunks 컬렉션 검색 + Max Roll-up 수행.
        use_toxic: True 이면 toxic_patterns 역방향 검색·독소 패턴 부착 수행.
    """
    logger.info(
        f"[review_contract] 검토 프로세스 시작: contract_type={contract_type.value}, "
        f"입력 조항 수={len(clauses)}개, 표준 코퍼스 크기={len(all_standard_clauses)}개"
    )

    if progress_callback:
        progress_callback(0, len(clauses), ProgressPhase.PREPARE)

    results: List[DeviationResult] = []
    matched_ids: set[str] = set()
    standards_by_id = {std.clause_id: std for std in all_standard_clauses}
    type_filter = {"contract_type": contract_type.value}
    # 검색·임베딩·리랭킹에는 정규화된 사본만 쓴다. user_clause 등 결과 표시용 원문은
    # clause.text 를 그대로 참조하므로 RDB/사용자 원본은 이 정규화의 영향을 받지 않는다
    # (마크다운 헤더·항호 기호 비대칭 — P_text_normalization.md).
    clause_texts = [normalize_for_search(clause.text) for clause in clauses]

    # ── 1. 배치 검색 ──
    if progress_callback:
        progress_callback(0, len(clauses), ProgressPhase.BATCH_SEARCH)
    logger.info("[review_contract] 1단계: 벡터 DB 배치 검색을 수행합니다 (표준/서브청크/독소).")
    clause_vectors = embedder.embed_documents(clause_texts) if clause_texts else []
    empty_batch: List[List[Dict[str, Any]]] = [[] for _ in clauses]
    std_batch = (
        retriever.hybrid_search_many(STANDARD_COLLECTION, clause_vectors, clause_texts, type_filter, top_k)
        if clause_texts else []
    )
    sub_batch = (
        retriever.hybrid_search_many(SUB_CHUNK_COLLECTION, clause_vectors, clause_texts, type_filter, top_k)
        if (clause_texts and use_sub_chunk) else empty_batch
    )
    toxic_batch = (
        retriever.hybrid_search_many(TOXIC_COLLECTION, clause_vectors, clause_texts, None, toxic_top_k)
        if (clause_texts and use_toxic) else empty_batch
    )
    logger.info(
        f"[review_contract] 배치 검색 완료: std_batch={len(std_batch)}건, "
        f"sub_batch={len(sub_batch)}건, toxic_batch={len(toxic_batch)}건"
    )

    # ── 2. 배치 재정렬 ──
    if progress_callback:
        progress_callback(0, len(clauses), ProgressPhase.RERANK)
    logger.info("[review_contract] 2단계: 조항별 재정렬(Rerank) 및 이탈(Deviation) 분류를 수행합니다.")
    std_hits_batch = reranker.rerank_many(clause_texts, std_batch, text_key="text", top_k=top_k)
    sub_hits_batch = reranker.rerank_many(clause_texts, sub_batch, text_key="text", top_k=top_k)
    toxic_hits_batch = reranker.rerank_many(
        clause_texts,
        [prepare_toxic_rerank_candidates(hits) for hits in toxic_batch],
        text_key="rerank_text",
        top_k=toxic_top_k,
    )

    for i, (clause, std_hits, sub_hits, toxic_hits) in enumerate(
        zip(clauses, std_hits_batch, sub_hits_batch, toxic_hits_batch), 1
    ):
        candidates = _clause_candidates(std_hits, standards_by_id, contract_type)
        sub_candidate: Optional[Tuple[StandardClause, float]] = None

        if sub_hits:
            sub_candidate = _sub_chunk_candidate(sub_hits, standards_by_id)
            if sub_candidate is not None:
                candidates.append(sub_candidate)

        # 독소 역방향 검색은 매칭 성패와 무관 (표준엔 없지만 사용자에게 해로운 EXTRA 조항 포착)
        toxic_patterns = _toxic_from_hits(toxic_hits, toxic_threshold) if toxic_hits else []

        # 매칭 판정: 후보가 아예 없으면 NO_MATCH, 임계 미달이면 EXTRA.
        # select_best_match는 이제 임계값과 무관하게 최고점 후보를 반환하므로(2차 LLM이
        # EXTRA도 비교 대상을 가질 수 있도록), matched_standard가 있다고 곧 NONE인 것은 아니다.
        if not std_hits and not sub_hits:
            deviation = Deviation.NO_MATCH
            matched_standard: Optional[StandardClause] = None
            score = 0.0
        else:
            matched_standard, score = select_best_match(candidates)
            deviation = classify_clause_deviation(matched_standard, score, match_threshold)

        # 표준조항 "커버됨" 기록(MISSING 탐지용)·연관위험 조회는 실제로 매칭이 확정된
        # NONE에서만 한다 — 임계 미달 근접후보(EXTRA)까지 커버로 치면 MISSING 탐지가 오염된다.
        if deviation == Deviation.NONE:
            matched_ids.add(matched_standard.clause_id)

        # todo graph 미구현 상태
        related_risks: List[str] = []
        if deviation == Deviation.NONE and graph is not None:
            related_risks = graph.get_related_risks(matched_standard.clause_id)

        results.append(DeviationResult(
            user_clause=clause.text,
            matched_standard=matched_standard,
            deviation=deviation,
            confidence=score,
            grounding=[],  # 1차 검토 NONE/EXTRA에는 법령 근거 부착 안 함
            toxic_patterns=toxic_patterns,
            related_risk_clauses=related_risks,
        ))

        if progress_callback:
            progress_callback(i, len(clauses), ProgressPhase.CLAUSE_REVIEW)

    logger.info(f"[review_contract] 조항별 재정렬/분류 완료. 매칭된 유니크 표준조항 수: {len(matched_ids)}개")

    # ── 3. 누락 탐지 ──
    if progress_callback:
        progress_callback(len(clauses), len(clauses), ProgressPhase.MISSING_DETECTION)
    logger.info("[review_contract] 3단계: 누락된 표준조항(MISSING) 탐지를 수행합니다.")
    missing_clauses = detect_missing_clauses(all_standard_clauses, matched_ids)
    logger.info(f"[review_contract] 누락 표준조항 탐지 결과: {len(missing_clauses)}건 누락 확인")
    # 계약 원문을 넘지 않는 정적 grounding만 이 요청 안에서 재사용한다. 함수가 끝나면
    # 즉시 폐기되어 사용자 계약 정보가 서버 전역 메모리에 남지 않는다.
    grounding_cache: Dict[Tuple[Category, ContractType], Tuple[GroundingLaw, ...]] = {}

    for missing_standard in missing_clauses:
        related = graph.get_related_risks(missing_standard.clause_id) if graph is not None else []
        results.append(DeviationResult(
            user_clause="",
            matched_standard=missing_standard,
            deviation=Deviation.MISSING,
            confidence=0.0,
            grounding=_grounding_for(
                grounder, missing_standard.category, contract_type, grounding_cache
            ),
            related_risk_clauses=related,
        ))

    logger.info(
        f"[review_contract] 검토 프로세스 완료: 최종 반환 결과 수={len(results)}건 "
        f"(사용자조항 판정={len(clauses)}건, 누락추가={len(missing_clauses)}건)"
    )
    return results
