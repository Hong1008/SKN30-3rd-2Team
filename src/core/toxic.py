from typing import Any, Dict, List, Tuple
from contracts.enums import ToxicPattern


def prepare_toxic_rerank_candidates(
    hits: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """독소 후보의 리랭커 입력만 보강한 사본을 만듭니다.

    검색·진단 원문인 ``text``는 유지하고, 제목이 있는 후보에는 ``rerank_text``를
    추가합니다. 본문이 없거나 문자열이 아니면 리랭커에 빈 입력을 넘기지 않도록
    명시적으로 실패합니다.
    """
    prepared: List[Dict[str, Any]] = []
    for index, hit in enumerate(hits):
        copied = dict(hit)
        raw_text = hit.get("text")
        title = hit.get("title")
        if not isinstance(raw_text, str) or not raw_text:
            hit_id = hit.get("id") or hit.get("pattern_id") or index
            raise ValueError(f"독소 후보 본문(text)이 없습니다: {hit_id}")
        copied["rerank_text"] = (
            f"검토 패턴: {title}\n예문: {raw_text}"
            if isinstance(title, str) and title
            else raw_text
        )
        prepared.append(copied)
    return prepared

def detect_toxic_patterns(
    matches: List[Tuple[ToxicPattern, float]],
    threshold: float
) -> List[ToxicPattern]:
    """
    [고도화 B: 독소조항 양방향 검색]
    표준 대비 이탈 탐지(사용자→표준 방향)와 별개로, 사용자 조항을
    독소 패턴 코퍼스(data/03_normalized/toxic_patterns.json)에도 매칭하는 역방향 검색입니다.
    "표준에는 없지만 사용자에게 불리한 추가 조항"을 잡아내기 위해 조항 단위 루프에서
    classify_clause_deviation과 병렬로 호출됩니다. 결과는 DeviationResult.toxic_patterns에 담깁니다.

    pipe가 Chroma toxic_patterns 컬렉션에서 검색한 (패턴, 점수) 쌍을 이 함수에 전달하면,
    여기서 임계치 필터링과 점수 내림차순 정렬만 수행합니다.

    Args:
        matches: pipe가 독소 패턴 컬렉션 검색으로 얻은 (ToxicPattern, 유사도 점수) 목록
        threshold: 독소조항으로 인정할 최소 점수

    Returns:
        감지된 독소조항 패턴 목록 (점수 내림차순)
    """
    detected: List[ToxicPattern] = []
    seen: set = set()
    # 점수가 높은 순으로 정렬 (같은 패턴이 여러 청크로 중복 검색될 수 있음)
    sorted_matches = sorted(matches, key=lambda x: x[1], reverse=True)

    for pattern, score in sorted_matches:
        if score < threshold:
            continue
        if pattern in seen:
            # 동일 패턴이 여러 후보로 중복 매칭돼도 최고점 1회만 남긴다
            # (하나의 독소패턴이 여러 서브청크로 색인돼 top-k 를 같은 값으로 채우는 현상 방지)
            continue
        seen.add(pattern)
        detected.append(pattern)

    return detected
