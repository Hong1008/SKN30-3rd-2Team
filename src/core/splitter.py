"""
항·호 단위 조항 분할기 + 검색용 표면형 정규화 (순수 함수)

오프라인(normalize.py) 과 런타임(review_pipe.py 커버리지 체크) 이 동일 조건을 공유합니다.
외부 의존성 없음 — re 표준 라이브러리만 사용.
"""
import re

# 분할 대상 판정 임계값 — 오프라인·런타임 공유 (한 곳에서만 관리)
_LARGE_CLAUSE_CHAR_LIMIT = 300
_LARGE_CLAUSE_SYMBOL_LIMIT = 3

# 항·호 기호 패턴
#  - ①~⑳ 원문자
#  - 줄 시작 숫자 + 마침표/닫는괄호: "1.", "1)", 앞에 대시가 붙는 "- 1)" 도 포함
#    (표준은 "1."·"①", 실계약은 "숫자)"·"- 1)" 형식을 자주 써서 둘 다 인식해야 한다.
#    v1_review Track B — 실계약 파싱 시 항 분할이 0건으로 축퇴하던 파서 결함 대응)
#  - 마침표/닫는괄호를 필수로 요구해 "2024 년" 같은 연도 숫자를 항 기호로 오인하지 않는다.
_SYMBOL_RE = re.compile(r"[①-⑳]")
_NUM_RE = re.compile(r"^[ \t]*-?[ \t]*[0-9]+[.)]", re.MULTILINE)
_SPLIT_RE = re.compile(r"(^[ \t]*-?[ \t]*[0-9]+[.)]|^[ \t]*[①-⑳])", re.MULTILINE)

# ── 검색용 표면형 정규화 (P_text_normalization.md) ─────────────────────────
# RDB 원본 텍스트는 절대 바꾸지 않는다. 이 함수의 출력은 임베딩·BM25 색인 직전에만
# 쓰이는 "검색 전용 사본"이다(호출부: pipe/build_index.py 의 documents, pipe/review_pipe.py 의
# clause_texts). 표준조항 코퍼스는 헤더가 있고 독소조항 코퍼스는 없어 리랭커 점수가 붕괴하던
# 비대칭(07-09 실측: 0.998→0.0003)을 없애는 것이 목적이므로, 제거 대상은 코퍼스마다 유무가
# 갈리는 "구조적 표식"(마크다운·조번호·항호 기호)으로만 좁힌다 — 제목·본문의 실제 어휘·숫자는
# 유지한다(제목은 의미 신호, 실제 숫자는 BM25·의미 매칭에 필요한 내용이기 때문).
_CLAUSE_HEADER_RE = re.compile(r"^\s*#*\s*제\d+조\s*[\(\（]([^\)\）\n]*)[\)\）]\s*\n?")
_LEADING_ENUM_STRIP_RE = re.compile(r"^[ \t]*-?[ \t]*(?:[0-9]+[.)]|[①-⑳])[ \t]*", re.MULTILINE)


def normalize_for_search(text: str) -> str:
    """검색·임베딩 입력 전용 표면형 정규화.

    - "### 제N조(제목)" 헤더에서 마크다운·조번호·괄호를 제거하고 제목 텍스트만 본문 앞에 병합한다
      (독소조항 코퍼스처럼 애초에 헤더가 없는 텍스트는 매칭되지 않아 그대로 통과한다).
    - 줄 시작의 항·호 열거 기호(①~⑳, "1.", "1)", "- 1)")를 제거한다.
    """
    match = _CLAUSE_HEADER_RE.match(text)
    if match:
        title = match.group(1).strip()
        rest = text[match.end():]
        # 개행으로 이어붙여야 rest 쪽 항·호 기호가 줄 시작(^) 위치를 유지해 아래 정규식에 걸린다.
        text = f"{title}\n{rest}".strip() if title else rest.strip()
    return _LEADING_ENUM_STRIP_RE.sub("", text).strip()


def is_large_clause(text: str) -> bool:
    """거대 조항(서브청킹 대상) 여부를 반환합니다.

    500자 초과 설계 원안(G_sub_chunk §1단계) 대신 실제 코퍼스 측정치 300자를
    임계값으로 사용합니다. 변경 시 이 상수만 수정하면 오프라인·런타임 모두 반영됩니다.
    """
    symbols = _SYMBOL_RE.findall(text)
    nums = _NUM_RE.findall(text)
    return len(text) > _LARGE_CLAUSE_CHAR_LIMIT or (len(symbols) + len(nums)) >= _LARGE_CLAUSE_SYMBOL_LIMIT


def split_into_sub_chunks(text: str) -> list[str]:
    """조항 텍스트를 항·호 기호 기준으로 분할합니다.

    거대 조항 조건 미달 시 원문 전체를 단일 원소 리스트로 반환합니다.
    빈 문자열 청크는 제외합니다.
    """
    if not is_large_clause(text):
        return [text]

    parts = _SPLIT_RE.split(text)

    chunks: list[str] = []

    # parts[0] 은 첫 기호 이전 선도 텍스트 (있을 수도 없을 수도)
    leading = parts[0].strip()
    if leading:
        chunks.append(leading)

    # 이후는 (기호, 내용) 쌍으로 반복
    for i in range(1, len(parts), 2):
        symbol = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        chunk = (symbol + body).strip()
        if chunk:
            chunks.append(chunk)

    return chunks if chunks else [text]
