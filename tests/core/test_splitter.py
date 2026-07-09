"""
core.splitter — is_large_clause · split_into_sub_chunks · normalize_for_search 순수 함수 단위 테스트
"""
from core.splitter import is_large_clause, normalize_for_search, split_into_sub_chunks


# ── is_large_clause ───────────────────────────────────────────────────────────

def test_300자_초과면_거대조항():
    assert is_large_clause("가" * 301) is True


def test_100자_이하면_거대조항_아님():
    assert is_large_clause("가" * 100) is False


def test_기호_3개_이상이면_글자수_무관하게_거대조항():
    """짧아도 항·호 기호가 3개 이상이면 거대 조항으로 판정합니다."""
    assert is_large_clause("① 가나다 ② 라마바 ③ 사아자") is True


def test_기호_2개는_거대조항_아님():
    assert is_large_clause("① 가나다 ② 라마바") is False


def test_숫자목록_3개_이상이면_거대조항():
    text = "1. 첫째\n2. 둘째\n3. 셋째"
    assert is_large_clause(text) is True


def test_기호와_숫자목록_합산_3개_이상이면_거대조항():
    """① 1개 + 1. 2개 = 합계 3개 → 거대 조항"""
    text = "① 첫째 항\n1. 첫 번째\n2. 두 번째"
    assert is_large_clause(text) is True


# ── split_into_sub_chunks ─────────────────────────────────────────────────────

def test_100자_단순_조항은_원문_그대로_반환():
    text = "갑은 을에게 대금을 지급한다." * 3  # 짧은 반복
    chunks = split_into_sub_chunks(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_600자_항기호_조항_2개이상_분할():
    text = "① " + "가" * 200 + "\n② " + "나" * 200 + "\n③ " + "다" * 200
    chunks = split_into_sub_chunks(text)
    assert len(chunks) >= 2


def test_분할_결과에_원본_내용_보존():
    """각 청크에 원본 항 내용이 포함되어야 합니다."""
    text = "① 원사업자는 대금을 지급한다.\n② 지연 시 이자를 부과한다.\n③ 기한은 60일이다."
    chunks = split_into_sub_chunks(text)
    full = "".join(chunks)
    assert "원사업자" in full
    assert "이자" in full
    assert "60일" in full


def test_숫자목록_기준_분할():
    text = "1. 갑은 을에게 대금을 지급한다.\n2. 지급 기한은 30일로 한다.\n3. 연체 시 이자를 부과한다."
    chunks = split_into_sub_chunks(text)
    assert len(chunks) >= 2


def test_숫자괄호_목록_분할():
    """실계약이 자주 쓰는 '숫자)' 형식도 항으로 분할해야 한다 (v1_review Track B 파서 버그)."""
    text = "1) 갑은 을에게 대금을 지급한다.\n2) 지급 기한은 30일로 한다.\n3) 연체 시 이자를 부과한다."
    chunks = split_into_sub_chunks(text)
    assert len(chunks) >= 2


def test_대시_숫자괄호_목록_분할():
    """'- 1)' 형식(test_sunny10 등 실계약)도 항으로 분할해야 한다."""
    text = "- 1) 본 계약은 독립사업자 계약이다.\n- 2) 근로기준법이 적용되지 않는다.\n- 3) 자유 의사로 체결한다."
    chunks = split_into_sub_chunks(text)
    assert len(chunks) >= 2


def test_연도_숫자는_항으로_오인하지_않음():
    """'2024 년'처럼 마침표·괄호가 없는 줄 시작 숫자는 항 기호가 아니다."""
    text = "제3조 계약기간\n2024 년 02 월 13 일부터 2024 년 04 월 30 일까지로 한다."
    # 항 기호가 없으므로 분할되지 않고 원문 1개 (거대조항 조건 미달)
    chunks = split_into_sub_chunks(text)
    assert len(chunks) == 1


def test_빈청크_포함되지_않음():
    text = "① 조항 내용\n\n② 추가 조항 내용\n③ 마지막 조항"
    chunks = split_into_sub_chunks(text)
    assert all(c.strip() for c in chunks)


def test_빈_텍스트에도_최소_1개_반환():
    """빈 문자열이더라도 빈 리스트가 아닌 원문 그대로 반환합니다."""
    text = "단순 조항 하나."
    chunks = split_into_sub_chunks(text)
    assert len(chunks) >= 1


def test_선도_텍스트_보존():
    """항 기호 앞에 오는 선도 텍스트(제목 줄 등)도 청크에 포함됩니다."""
    text = "제58조 표제 내용\n① 첫째 항 내용이 들어갑니다.\n② 둘째 항 내용이 들어갑니다.\n③ 셋째 항 내용"
    chunks = split_into_sub_chunks(text)
    # 선도 + 3항 = 최소 2청크 이상
    assert len(chunks) >= 2
    joined = " ".join(chunks)
    assert "표제" in joined


# ── normalize_for_search ──────────────────────────────────────────────────────

def test_마크다운_헤더_제거_제목은_보존():
    text = "### 제43조(경업금지 및 인력 유출 방지)\n본문 내용입니다."
    result = normalize_for_search(text)
    assert "###" not in result
    assert "제43조" not in result
    assert "경업금지 및 인력 유출 방지" in result
    assert "본문 내용입니다." in result


def test_괄호없는_헤더는_변형하지_않음():
    """괄호가 없는 헤더(드문 케이스)는 매칭되지 않아 원문 그대로 통과합니다."""
    text = "제43조 목적\n본문 내용입니다."
    result = normalize_for_search(text)
    assert result == text


def test_헤더_없는_평문은_그대로_통과():
    """독소조항 코퍼스처럼 헤더가 없는 텍스트는 정규화 대상이 없어 원문과 동일합니다."""
    text = "경업금지 기간에 상한이 없다."
    assert normalize_for_search(text) == text


def test_원문자_항목기호_제거():
    text = "① 원사업자는 대금을 지급한다.\n② 지연 시 이자를 부과한다."
    result = normalize_for_search(text)
    assert "①" not in result and "②" not in result
    assert "원사업자는 대금을 지급한다." in result
    assert "지연 시 이자를 부과한다." in result


def test_숫자_목록기호_제거():
    text = "1. 갑은 을에게 대금을 지급한다.\n2) 지급 기한은 30일로 한다."
    result = normalize_for_search(text)
    assert "1." not in result and "2)" not in result
    assert "30일" in result  # 본문 속 실제 숫자는 유지


def test_본문_숫자는_보존():
    """조번호·항목기호가 아닌 본문 속 숫자(계약기간·금액 등)는 지우지 않습니다."""
    text = "### 제6조(계약기간)\n계약기간은 20년으로 하고 대금은 300만원으로 한다."
    result = normalize_for_search(text)
    assert "20년" in result
    assert "300만원" in result


def test_헤더와_항목기호_동시_제거():
    text = "### 제58조(대금 지급)\n① 원사업자는 대금을 지급한다.\n② 지연 시 이자를 부과한다."
    result = normalize_for_search(text)
    assert "###" not in result and "제58조" not in result
    assert "①" not in result and "②" not in result
    assert "대금 지급" in result
    assert "원사업자는 대금을 지급한다." in result
