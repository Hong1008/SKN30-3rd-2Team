"""core.detect_toxic_patterns 규격 테스트 — 독소조항 임계 필터 (고도화 B)."""
from contracts.enums import ToxicPattern
from core import detect_toxic_patterns, prepare_toxic_rerank_candidates


def test_임계치_이상만_점수순으로():
    matches = [
        (ToxicPattern.IP_TOTAL_FREE, 0.9),
        (ToxicPattern.NONCOMPETE_EXCESS, 0.3),
        (ToxicPattern.PAYMENT_DELAY_UNFAIR, 0.7),
    ]
    result = detect_toxic_patterns(matches, threshold=0.5)
    # 0.3 은 탈락, 나머지는 점수 내림차순
    assert result == [ToxicPattern.IP_TOTAL_FREE, ToxicPattern.PAYMENT_DELAY_UNFAIR]


def test_모두_미달이면_빈결과():
    matches = [(ToxicPattern.IP_TOTAL_FREE, 0.2)]
    assert detect_toxic_patterns(matches, threshold=0.5) == []


def test_빈_입력은_빈결과():
    assert detect_toxic_patterns([], threshold=0.5) == []


def test_리랭크_입력은_text를_보존하고_rerank_text만_보강한다():
    hit = {
        "id": "toxic-1", "title": "저작권 전부 무상 귀속",
        "text": "수급인은 저작재산권을 전부 양도한다.", "pattern": "IP_TOTAL_FREE",
    }
    result = prepare_toxic_rerank_candidates([hit])

    assert result[0]["text"] == hit["text"]
    assert result[0]["rerank_text"] == (
        "검토 패턴: 저작권 전부 무상 귀속\n예문: 수급인은 저작재산권을 전부 양도한다."
    )
    assert "rerank_text" not in hit


def test_리랭크_입력_필드가_없으면_원문을_보존한다():
    hit = {"id": "toxic-2", "text": "원문 후보"}
    result = prepare_toxic_rerank_candidates([hit])

    assert result == [{"id": "toxic-2", "text": "원문 후보", "rerank_text": "원문 후보"}]


def test_리랭크_입력_text가_없으면_명시적으로_실패한다():
    import pytest

    with pytest.raises(ValueError, match="toxic-3"):
        prepare_toxic_rerank_candidates([{"id": "toxic-3", "title": "제목"}])
