"""WorkShield 발표용 스트림릿 데모 앱 (MCP 클라이언트 연동판).

두 서버 체계:
    [터미널 1 · 루트]  just run-mcp streamable-http 8000   ← MCP 서버
    [터미널 2 · 루트]  uv run --project demo streamlit run demo/streamlit_app.py

연결 방식은 demo/src/config.py 의 APP_ENV 를 따른다.
    prod  (데모 기본) → Streamable HTTP 로 WORKSHIELD_MCP_URL 접속 (두 서버 체계)
    local             → stdio: 클라이언트가 MCP 서버를 서브프로세스로 직접 기동

실서버 호출 실패(서버 미기동·파이프라인 오류) 또는 파일 미업로드 시에는
mock 시나리오로 폴백하고, 화면에 데이터 출처(실서버/mock)를 표시한다.

남은 훅:
  * generate_llm_summary()   — 현재 고정 문구 → LLM 연결 예정 (데모는 LLM 허용)
  * load_ablation_metrics()  — 현재 None → src/eval 결과 연결 예정
"""

import asyncio
import base64
import os
import socket
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# demo/src 를 모듈 검색 경로에 추가 (config · workshield_mcp_client import 용)
DEMO_SRC = Path(__file__).resolve().parent / "src"
if str(DEMO_SRC) not in sys.path:
    sys.path.insert(0, str(DEMO_SRC))

# 데모 기본 연결 모드 = HTTP 두 서버 체계.
# (셸/.env 에서 APP_ENV 를 명시하면 그 값이 우선. local 로 바꾸면 stdio 자동 기동)
os.environ.setdefault("APP_ENV", "prod")

import streamlit as st
from pydantic import BaseModel, Field

from config import app_env, WORKSHIELD_MCP_URL
from workshield_mcp_client import WorkShieldMCPClient

# ──────────────────────────────────────────────────────────────
# 이탈 유형 상수 (서버 응답의 Deviation enum 값과 동일한 문자열)
# 데모는 MCP 응답(JSON)만 소비하므로 루트 contracts 패키지에 의존하지 않는다.
# ──────────────────────────────────────────────────────────────

DEV_NONE = "NONE"
DEV_CHANGED = "CHANGED"
DEV_MISSING = "MISSING"
DEV_EXTRA = "EXTRA"
DEV_NO_MATCH = "NO_MATCH"

# ──────────────────────────────────────────────────────────────
# 화면용 데이터 모델 — UI 는 이 모델만 바라본다
# ──────────────────────────────────────────────────────────────


class GroundingRef(BaseModel):
    """법령 근거 참조 (korean-law-mcp 결과)."""

    law_name: str
    article: str
    source: str = ""


class ClauseCard(BaseModel):
    """검토 결과 카드 1장."""

    title: str
    deviation: str
    confidence: Optional[float] = None
    body_user: Optional[str] = None
    """내 계약서 조항 본문 (좌우 비교용)"""
    body_std: Optional[str] = None
    """매칭된 표준조항 본문 (좌우 비교용)"""
    std_ref: Optional[str] = None
    """표준 출처 좌표 (파일 · 조번호)"""
    note: Optional[str] = None
    toxic_pattern: Optional[str] = None
    grounding: list[GroundingRef] = Field(default_factory=list)


class ReviewDemoResult(BaseModel):
    """화면에 뿌릴 검토 결과 전체."""

    contract_type: str
    total_user_clauses: int
    none_titles: list[str]
    """이탈 없음(NONE) 조항 제목 목록"""
    cards: list[ClauseCard]
    """CHANGED / MISSING / EXTRA / NO_MATCH 카드"""


# ──────────────────────────────────────────────────────────────
# 실서버 호출 (WorkShieldMCPClient 경유)
# ──────────────────────────────────────────────────────────────


class DemoServerError(RuntimeError):
    """실서버 검토 실패 — mock 폴백 트리거용."""


# MCP 호출 제한 시간(초). 로컬 CPU 서버는 첫 호출에 모델 로드가 포함되므로 너무 짧게 잡지 말 것.
MCP_TIMEOUT_SEC = 300

# 서버 도달성 사전 확인 타임아웃(초). 짧게 — "꺼져 있음"을 빨리 판단하기 위함.
REACHABILITY_CHECK_SEC = 2.0


def _preflight_check() -> None:
    """HTTP 모드일 때, mcp 클라이언트를 열기 전에 TCP 레벨로 서버 도달성만 먼저 확인한다.

    이 체크를 생략하고 서버가 꺼진 채로 곧장 mcp 클라이언트를 열면, mcp SDK 의
    streamable_http_client(anyio 기반)가 "연결 실패 + 정리(cleanup)"가 겹치는 순간
    취소 범위(cancel scope)가 태스크 경계를 넘나들며 깨져 매우 지저분한 크래시
    (BaseExceptionGroup 안에 GeneratorExit)를 낸다 — asyncio.wait_for 유무와 무관하게
    재현되는 mcp/anyio/httpx 조합의 알려진 문제 유형. 순수 소켓 연결로 먼저 걸러내면
    이 버그 경로 자체를 타지 않는다.
    """
    if app_env == "local":
        return  # stdio 모드는 서브프로세스 기동이라 TCP 체크 대상이 아님
    parsed = urlparse(WORKSHIELD_MCP_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=REACHABILITY_CHECK_SEC):
            pass
    except OSError as e:
        raise DemoServerError(
            f"MCP 서버({host}:{port})에 연결할 수 없습니다 — 서버가 꺼져 있는지 확인하세요. ({e})"
        ) from e


def _mcp_call(coro_factory):
    """MCP 도구 한 개를 동기 방식으로 호출한다 (호출마다 세션 개폐).

    HTTP 모드에선 가볍지만, stdio 모드에선 호출마다 서버 서브프로세스를 새로
    기동하므로 느리다 — 데모 기본은 HTTP(두 서버 체계)라는 전제.
    타임아웃·연결 실패는 httpx 계층에서 일반 Exception 으로 올라오므로,
    호출부(run_review_pipeline)의 mock 폴백이 그대로 잡아낸다.
    """
    _preflight_check()

    async def _run():
        async with WorkShieldMCPClient(read_timeout=MCP_TIMEOUT_SEC) as client:
            return await coro_factory(client)

    try:
        return asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:  # noqa: BLE001 — mcp/anyio 조합이 간헐적으로 BaseException 계열
        # (CancelledError, BaseExceptionGroup 등)을 흘려보낼 수 있어 최후 안전망으로 넓게 잡는다.
        # 발표 중 화면이 죽는 것보다 mock 폴백이 낫다는 판단.
        raise DemoServerError(f"MCP 호출 중 예기치 않은 오류: {_snippet(str(e), 100)}") from e


def _call_review_tool(file_bytes: bytes, file_name: str, contract_type: str) -> dict:
    """MCP review_contract 도구를 동기 방식으로 호출한다.

    파일은 base64 로 인코딩해 전달하므로 HTTP·stdio 어느 연결에서도 동작한다.
    """
    b64 = base64.b64encode(file_bytes).decode("ascii")
    return _mcp_call(
        lambda c: c.review_contract(
            contract_type=contract_type, file_content=b64, file_name=file_name
        )
    )


def _snippet(text: str, limit: int = 22) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def _convert_server_response(data: dict, contract_type: str) -> ReviewDemoResult:
    """서버 ReviewContractResponse(JSON dict) → 화면 모델 변환."""
    status = data.get("status")
    if status != "OK":
        raise DemoServerError(data.get("message") or f"서버 응답 상태 {status}")

    none_titles: list[str] = []
    cards: list[ClauseCard] = []
    user_clause_count = 0

    for item in data.get("results", []):
        deviation = item.get("deviation", DEV_NO_MATCH)
        user_clause = (item.get("user_clause") or "").strip()
        std = item.get("matched_standard") or {}
        std_title = (std.get("title") or "").strip()

        if deviation != DEV_MISSING:
            user_clause_count += 1

        if deviation == DEV_NONE:
            none_titles.append(std_title or _snippet(user_clause))
            continue

        if deviation == DEV_MISSING:
            title = f"표준 · {std_title}" if std_title else "표준 조항 (제목 없음)"
        else:
            title = std_title or _snippet(user_clause)

        toxic = item.get("toxic_patterns") or []
        toxic_str = ", ".join(
            t.get("pattern_id", str(t)) if isinstance(t, dict) else str(t) for t in toxic
        )

        cards.append(
            ClauseCard(
                title=title,
                deviation=deviation,
                confidence=item.get("confidence"),
                body_user=user_clause or None,
                body_std=(std.get("text") or None) if deviation == DEV_CHANGED else None,
                std_ref=std.get("source") or None,
                toxic_pattern=toxic_str or None,
                grounding=[
                    GroundingRef(
                        law_name=g.get("법령명", ""),
                        article=g.get("조번호", ""),
                        source=g.get("출처", ""),
                    )
                    for g in item.get("grounding", [])
                ],
            )
        )

    return ReviewDemoResult(
        contract_type=contract_type,
        total_user_clauses=user_clause_count,
        none_titles=none_titles,
        cards=cards,
    )


# ──────────────────────────────────────────────────────────────
# mock 폴백 시나리오 (서버 미기동·오류·파일 미업로드 시)
# ──────────────────────────────────────────────────────────────


def mock_review_result(contract_type: str) -> ReviewDemoResult:
    """HTML 목업과 동일한 고정 시나리오."""
    return ReviewDemoResult(
        contract_type=contract_type,
        total_user_clauses=18,
        none_titles=[
            "제1조 목적", "제2조 용어의 정의", "제3조 계약기간", "제4조 성실 의무",
            "제6조 검수", "제7조 대금", "제8조 지연 배상", "제10조 비밀유지",
            "제11조 자료 제공", "제13조 하자보수", "외 4건 …",
        ],
        cards=[
            ClauseCard(
                title="제12조 · 저작권의 귀속",
                deviation=DEV_CHANGED,
                confidence=0.82,
                body_user="용역 수행 과정에서 발생한 결과물의 **모든 저작권(2차적저작물작성권 포함)은 발주자에게 귀속**된다.",
                body_std="결과물의 저작권 귀속은 **상호 협의하여 정하며**, 2차적저작물작성권은 **별도 합의 없이 이전되지 않는다**.",
                std_ref="SW프리랜서 표준계약서 제12조 (sw_std-art12)",
                grounding=[GroundingRef(law_name="저작권법", article="제5조", source="korean-law-mcp")],
            ),
            ClauseCard(
                title="제5조 · 과업의 범위",
                deviation=DEV_CHANGED,
                confidence=0.77,
                note="표준(sw_std-art5)과 매칭됐지만 과업 변경 시 협의 절차 문구가 다릅니다.",
                std_ref="SW프리랜서 표준계약서 제5조",
            ),
            ClauseCard(
                title="표준 제9조 · 대금 지급 시기",
                deviation=DEV_MISSING,
                note="내 계약서에서 대응 조항을 찾지 못했습니다.",
                std_ref="SW프리랜서 표준계약서 제9조",
            ),
            ClauseCard(title="표준 제14조 · 계약의 해지", deviation=DEV_MISSING, std_ref="SW프리랜서 표준계약서 제14조"),
            ClauseCard(title="표준 제16조 · 분쟁의 해결", deviation=DEV_MISSING, std_ref="SW프리랜서 표준계약서 제16조"),
            ClauseCard(
                title="제15조 · 권리의 귀속 특약",
                deviation=DEV_EXTRA,
                toxic_pattern="IP_TOTAL_FREE (저작권 전부 무상귀속 · toxic-ip_total_free)",
                note='"모든 지식재산권은 어떠한 대가 없이 갑에게 영구 귀속되며…" — 표준에 없는 추가 조항이 독소 패턴과 매칭됐습니다.',
            ),
            ClauseCard(
                title="제17조 · 기타 특약",
                deviation=DEV_NO_MATCH,
                note="표준조항·독소 패턴 어디에도 충분히 매칭되지 않았습니다. 빈 응답 대신 NO_MATCH 명시 표식을 반환하고, 판단을 생성하지 않습니다.",
            ),
        ],
    )


def run_review_pipeline(
    file_bytes: Optional[bytes],
    file_name: Optional[str],
    contract_type: str,
) -> tuple[ReviewDemoResult, str]:
    """검토 실행. (결과, 데이터 출처 설명) 을 반환한다.

    파일이 업로드됐으면 실서버(MCP review_contract)를 호출하고,
    미업로드·호출 실패 시 mock 시나리오로 폴백한다.
    """
    if not file_bytes or not file_name:
        return mock_review_result(contract_type), "mock 시나리오 (파일 미업로드)"

    try:
        data = _call_review_tool(file_bytes, file_name, contract_type)
        # 클라이언트 래퍼는 McpError 를 {"status": "ERROR"} 로 변환해 돌려준다
        if data.get("status") == "ERROR":
            raise DemoServerError(data.get("message", "MCP 호출 실패"))
        return _convert_server_response(data, contract_type), f"실서버 ({app_env})"
    except Exception as e:  # 발표 안전장치: 어떤 실패든 mock 으로 데모 지속
        return mock_review_result(contract_type), f"mock 폴백 — 실서버 호출 실패: {_snippet(str(e), 80)}"


def _run_live_pipeline_calls(
    file_bytes: bytes, file_name: str, contract_type: str, b64: str
) -> tuple[dict, dict]:
    """parse_contract → review_contract 를 세션 하나에서 순차 실행한다.

    이전에는 도구마다 _mcp_call() 을 따로 호출해 매번 세션을 새로 열고 닫았다
    (stdio 모드에선 서브프로세스까지 매번 재기동). 세션을 한 번만 열어 그 안에서
    두 호출을 순차 await 하면 연결·핸드셰이크 재개설 오버헤드가 한 번으로 줄어든다.
    """
    _preflight_check()

    async def _run():
        async with WorkShieldMCPClient(read_timeout=MCP_TIMEOUT_SEC) as client:
            parsed = await client.parse_contract(
                file_content=b64, file_name=file_name, contract_type=contract_type
            )
            data = await client.review_contract(
                contract_type=contract_type, file_content=b64, file_name=file_name
            )
            return parsed, data

    try:
        return asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:  # noqa: BLE001 — _mcp_call 과 동일한 최후 안전망
        raise DemoServerError(f"MCP 호출 중 예기치 않은 오류: {_snippet(str(e), 100)}") from e


def run_live_review(
    file_bytes: bytes,
    file_name: str,
    contract_type: str,
) -> tuple[ReviewDemoResult, str]:
    """업로드 문서를 검토하며 로그를 실시간 렌더링한다.

    실제 MCP 호출은 parse_contract·review_contract 두 번뿐이며, 하나의 세션 안에서
    순차 실행한다 (match_clause 는 review_contract 배치 안에서 이미 수행되므로 별도
    호출 없이 연출 로그로만 표시 — 중복 파싱·왕복 제거).
    """
    b64 = base64.b64encode(file_bytes).decode("ascii")
    steps_done: list[tuple[bool, str, str, Optional[str]]] = []

    def _show(is_tool: bool, name: str, desc: str, mono: Optional[str], last: bool = False) -> None:
        steps_done.append((is_tool, name, desc, mono))
        _render_step(len(steps_done), is_tool, name, desc, mono, last=last)

    st.markdown("##### 파이프라인 진행 로그")
    with st.container(border=True):
        st.caption(
            f"업로드 문서({file_name})가 결과로 나오기까지 — 실제 서버 호출 로그 · "
            + _badge("MCP 도구", "#DDEEFB;color:#2E6E9E")
            + _badge("내부 단계", "#F2F3FB;color:#5F6779"),
            unsafe_allow_html=True,
        )

        try:
            with st.spinner("parse_contract → review_contract 실행 중… (단일 세션)"):
                parsed, data = _run_live_pipeline_calls(file_bytes, file_name, contract_type, b64)

            # 1) parse_contract — 실제 조항 분해
            if parsed.get("status") == "OK":
                clauses = parsed.get("clauses", [])
                titles = " · ".join(
                    f"{c.get('num', '')} {c.get('title', '')}".strip() for c in clauses[:4]
                )
                _show(True, "parse_contract", f"계약서를 조항 {len(clauses)}개로 분해",
                      titles + (" …" if len(clauses) > 4 else ""))
            else:
                _show(True, "parse_contract",
                      f"파싱 결과 없음 ({parsed.get('status')}) — {parsed.get('message', '')}", None)

            # 2) embed — 내부 단계 (서버가 중간값을 노출하지 않아 설명만 표시)
            _show(False, "embed", "각 조항을 dense 1024dim + sparse 표현으로 변환 (bge-m3)", None)

            # 3) match_clause — review_contract 배치 안에서 이미 수행됨 (연출만 표시, 재호출 없음)
            _show(True, "match_clause", "하이브리드 검색으로 표준조항 top-5 추출 → 리랭커로 재정렬", None)

            # 4) deviation — 내부 단계
            _show(False, "deviation", "매칭 확정 → 표준 본문과 차이 감지 → 이탈 판정 · 독소 패턴 대조", None)

            # 5) get_grounding — review_contract 내부에서 함께 실행됨을 안내
            _show(True, "get_grounding", "korean-law-mcp 호출 → 이탈 조항 카테고리별 법령 조문 부착", None)

            # 6) review_contract — 전체 검토 (최종 결과의 단일 진실원)
            if data.get("status") == "ERROR":
                raise DemoServerError(data.get("message", "MCP 호출 실패"))
            result = _convert_server_response(data, contract_type)
            _show(True, "review_contract",
                  f"조항별 최종 응답 조립 완료 (검토 후보 {len(result.cards)}건 · 일치 {len(result.none_titles)}건) "
                  "→ 상단 「검토 결과」에 표시", None, last=True)
            source = f"실서버 ({app_env})"
        except Exception as e:
            result = mock_review_result(contract_type)
            source = f"mock 폴백 — 실서버 호출 실패: {_snippet(str(e), 80)}"
            _show(True, "review_contract", "실서버 검토 실패 → mock 시나리오로 결과 표시", None, last=True)

    st.session_state.live_steps = steps_done
    return result, source


def generate_llm_summary(result: ReviewDemoResult) -> str:
    """검출 결과만 인용하는 근거 기반 요약.

    TODO(팀): LLM 연결 (데모는 LLM 허용 — AGENTS.md 절대 규칙 1의 예외).
    프롬프트에는 result 의 검출 결과·법령 조문만 넣고, 자체 법률 해석을 생성하지
    않도록 제한한다. 근거 없는 항목은 "판단하지 않습니다"로 답하게 할 것.
    """
    return (
        "이 계약서는 저작권 귀속 조항(제12조)이 표준조항과 달라 검토 후보이며 "
        "[근거: 저작권법 제5조], 표준의 대금 지급 시기 조항에 대응하는 내용이 없습니다. "
        "제15조는 알려진 독소 패턴(저작권 전부 무상귀속)과 일치합니다. "
        "제17조는 표준·법령에서 근거를 찾지 못해 판단하지 않습니다."
    )


def load_ablation_metrics() -> Optional[dict[str, float]]:
    """리트리벌 ablation 측정값 로드.

    TODO(팀): 골든셋 확정 후 src/eval 결과를 읽어
    {"bm25": 0.xx, "dense": 0.xx, "hybrid": 0.xx, "hybrid_rerank": 0.xx} 반환.
    None 이면 화면에는 "측정 예정"으로 표시된다.
    """
    return None


# ──────────────────────────────────────────────────────────────
# 스타일 (HTML 목업의 파스텔 연보라 팔레트)
# ──────────────────────────────────────────────────────────────

PALETTE_CSS = """
<style>
  .stApp { background: #EDEFFA; }
  h1, h2, h3 { color: #3E4557; }
  div[data-testid="stExpander"] {
    background: #FFFFFF; border-radius: 14px;
    box-shadow: 0 1px 3px rgba(70,80,140,.06), 0 4px 14px rgba(70,80,140,.07);
  }
  .ws-tile { border-radius: 12px; padding: 10px; text-align: center;
             height: 92px; display: flex; flex-direction: column; justify-content: center; }
  .ws-tile .lbl { font-size: 12px; margin: 0; font-weight: 500; }
  .ws-tile .val { font-size: 20px; font-weight: 600; margin: 2px 0 0; }
  .ws-tile .sub { font-size: 10px; margin: 0; opacity: .75; }
  .ws-badge { display:inline-block; font-size:11px; font-weight:500;
              padding:2px 8px; border-radius:20px; margin-right:4px; }
  .ws-llm { border:1px dashed #C9CCE4; border-radius:14px; padding:14px 18px;
            background:#F2F3FB; color:#5F6779; font-size:14px; margin-bottom:16px; }
  .ws-step { border-left:2px solid #C9CCE4; margin-left:14px;
             padding:0 0 18px 20px; position:relative; }
  .ws-step .num { position:absolute; left:-15px; top:-2px; width:28px; height:28px;
                  border-radius:50%; background:#6E76F2; color:#fff; font-size:13px;
                  font-weight:600; display:flex; align-items:center; justify-content:center; }
  .ws-step .num.done { background:#5BB97F; }
  .ws-step p { margin:4px 0 0; font-size:13.5px; color:#5F6779; }
  .ws-step code { background:#F2F3FB; border-radius:6px; padding:2px 6px; font-size:12px; }
  /* 결과 그룹 카드 크기 통일: 접힌 헤더 높이 고정 + 펼친 본문 높이 고정(내부 스크롤) */
  div[data-testid="stExpander"] details summary { min-height: 52px; align-items: center; }
  div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
    height: 320px; overflow-y: auto;
  }
  /* bordered 컨테이너를 HTML 목업의 흰 카드처럼 */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF; border-radius: 18px;
    box-shadow: 0 1px 3px rgba(70,80,140,.06), 0 4px 14px rgba(70,80,140,.07);
  }
</style>
"""

# 이탈 유형별 화면 메타: (라벨 점, 한 줄 설명, "배경색;글자색")
DEVIATION_META: dict[str, tuple[str, str, str]] = {
    DEV_NONE: ("🟢", "표준과 일치, 검토 후보 아님", "#E4F3E9;color:#2E7D4F"),
    DEV_CHANGED: ("🔵", "표준과 매칭됐지만 본문이 다른 조항", "#E7E9FD;color:#4F57C9"),
    DEV_MISSING: ("🔴", "표준에는 있는데 내 계약서에 없는 조항", "#F7E2E2;color:#B25454"),
    DEV_EXTRA: ("🟡", "표준에 없는 추가 조항 (독소 패턴 대조 포함)", "#FFF3D6;color:#8A6A1F"),
    DEV_NO_MATCH: ("⚪", "근거를 찾지 못해 판단하지 않은 조항", "#F2F3FB;color:#5F6779"),
}

# 파이프라인 단계: (MCP 도구 여부, 이름, 설명, 로그 예시)
PIPELINE_STEPS: list[tuple[bool, str, str, Optional[str]]] = [
    (True, "parse_contract", "계약서를 조항 단위로 분해",
     '[{"idx":1,"조번호":"제1조","title":"목적"}, {"idx":12,"조번호":"제12조","title":"저작권의 귀속"}, ...]'),
    (False, "embed", "각 조항을 dense 1024dim + sparse 표현으로 변환 (bge-m3)", None),
    (True, "match_clause", "하이브리드 검색으로 표준조항 top-5 추출 → 리랭커로 재정렬",
     "1. sw_std-art12  score 0.79 → 0.91 (재정렬 후 1위)\n2. sw_std-art14  score 0.81 → 0.63"),
    (False, "deviation", "매칭 확정 → 표준 본문과 차이 감지 → 이탈 판정 · 독소 패턴 대조", None),
    (True, "get_grounding", "korean-law-mcp 호출 → 관련 법령 조문 조회", None),
    (True, "review_contract", "조항별 최종 응답(매칭·이탈·근거) 조립 완료 → 상단 「검토 결과」에 표시", None),
]

# 계약 유형: MVP 활성 3종 (값은 서버 ContractType enum 문자열과 동일) + 추후 업데이트 예정
ACTIVE_TYPES: dict[str, str] = {
    "SW 프리랜서 표준계약서 (SW_FREELANCE)": "SW_FREELANCE",
    "상용SW 공급·개발·구축 하도급 (SI_SUBCONTRACT)": "SI_SUBCONTRACT",
    "상용SW 유지관리 하도급 (SM_SUBCONTRACT)": "SM_SUBCONTRACT",
}
FUTURE_TYPES = ["방송산업", "만화산업", "영화산업", "건설산업", "프리랜서 강사"]

# 파이프라인 로그 단계별 등장 간격(초). 발표 템포에 맞게 조절.
# (주의: 대입문 아래 독립 문자열은 스트림릿 매직이 화면에 출력하므로 주석으로 유지할 것)
STEP_SEC = 0.7


# ──────────────────────────────────────────────────────────────
# 렌더링
# ──────────────────────────────────────────────────────────────


def _badge(text: str, style: str) -> str:
    return f'<span class="ws-badge" style="background:{style}">{text}</span>'


def render_sidebar() -> None:
    """데모 소개 + 연결 상태 사이드바 (접기 가능)."""
    with st.sidebar:
        st.markdown("### 🛡️ 이 데모는")
        st.markdown(
            "프리랜서 용역계약서를 표준계약서와 **조항 단위로 비교**해 이탈(누락·추가·변경)을 "
            "탐지하고, 모든 결과에 표준조항·법령 출처를 붙여 반환하는 RAG 파이프라인 데모입니다."
        )
        st.markdown(
            "근거가 없는 항목은 판단하지 않습니다 — 매칭 실패는 빈 응답 대신 "
            "**NO_MATCH 명시 표식**으로 반환됩니다."
        )
        st.caption('모든 결과는 "검토가 필요한 후보"이며, 위법·불리함을 단정하지 않습니다.')
        st.divider()
        st.markdown("**연결 상태**")
        if app_env == "local":
            st.caption("stdio — 검토 시 MCP 서버를 서브프로세스로 자동 기동")
        else:
            st.caption(f"HTTP — {WORKSHIELD_MCP_URL}")
            st.caption("서버 실행: `just run-mcp streamable-http 8000`")
        source = st.session_state.get("data_source")
        if source:
            st.caption(f"최근 검토 데이터: {source}")


def render_form() -> None:
    """검토 시작 카드: 업로드 + 계약 유형 + 서버 구성 (통합, 흰 카드)."""
    st.markdown("##### 검토 시작")
    with st.container(border=True):
        left, right = st.columns([1.1, 1], gap="large")

        with left:
            uploaded = st.file_uploader(
                "계약서 업로드",
                type=["pdf", "hwp", "hwpx", "doc", "docx"],
                help="PDF · HWP · WORD 파일 (스캔 이미지 제외)",
            )
            st.caption("🔒 업로드된 계약서 파일은 저장하지 않으며, 검토가 끝나면 즉시 파기됩니다.")
            if uploaded is not None:
                st.caption(f"📄 {uploaded.name} · {uploaded.size:,} bytes — 실서버로 검토합니다.")
            else:
                st.caption("파일 없이 실행하면 mock 시나리오로 시연됩니다.")

            options = list(ACTIVE_TYPES.keys()) + [
                f"{t} 표준계약서 — 추후 업데이트 예정" for t in FUTURE_TYPES
            ]
            type_label = st.selectbox("표준계약 유형", options)
            is_future = type_label not in ACTIVE_TYPES
            if is_future:
                st.warning("이 유형은 추후 업데이트 예정입니다. 현재 지원 중인 유형을 선택해 주세요.", icon="🚧")

            st.toggle(
                "상세 파이프라인 로그 (단계별 실호출 — 검토 시간 2배 이상 증가)",
                value=False,
                key="live_log",
                help="켜면 parse·match 를 개별 호출해 로그에 실제 조항 수·매칭 점수가 표시되지만, "
                "서버 작업이 중복 실행되어 오래 걸립니다. 발표 기본은 꺼짐(검토 1회 호출) 권장.",
            )

            already_done = st.session_state.phase == "done"
            if st.button(
                "다시 검토" if already_done else "표준 대비 검토 시작",
                type="primary",
                use_container_width=True,
                disabled=is_future,
            ):
                st.session_state.upload_bytes = uploaded.getvalue() if uploaded else None
                st.session_state.upload_name = uploaded.name if uploaded else None
                st.session_state.contract_type = ACTIVE_TYPES[type_label]
                st.session_state.job_token = time.time()  # 재실행 가드용 실행 식별자
                st.session_state.phase = "running"
                st.rerun()

        with right:
            st.markdown("**서버 구성 사양**")
            rows = [
                ("임베딩 모델", "bge-m3", "조합"),
                ("리랭커", "bge-reranker-v2-m3", "조합"),
                ("RDB (SQLite)", "표준조항 273건 적재 (4종·판본별)", None),
                ("벡터 DB (Chroma)", "서브청크 1,898건 · dense+sparse", None),
                ("독소조항 패턴셋", "40건 큐레이션", "직접 구축"),
                ("korean-law-mcp", "연동됨", "조합"),
                ("이탈 탐지 로직 · 스키마", "", "직접 구축"),
            ]
            for name, value, tag in rows:
                badge = ""
                if tag == "조합":
                    badge = _badge("조합", "#DDEEFB;color:#2E6E9E")
                elif tag == "직접 구축":
                    badge = _badge("직접 구축", "#E7E9FD;color:#4F57C9")
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:7px 0;'
                    f'border-bottom:0.5px solid #E3E5F2;font-size:14px;color:#3E4557">'
                    f"<span>{name}</span><span>{value} {badge}</span></div>",
                    unsafe_allow_html=True,
                )


def _render_step(idx: int, is_tool: bool, name: str, desc: str, mono: Optional[str], last: bool) -> None:
    num = '<div class="num done">✓</div>' if last else f'<div class="num">{idx}</div>'
    badge = (
        _badge(name, "#DDEEFB;color:#2E6E9E") if is_tool
        else _badge(name, "#F2F3FB;color:#5F6779")
    )
    mono_html = f"<p><code>{mono}</code></p>" if mono else ""
    st.markdown(
        f'<div class="ws-step">{num}{badge}<p>{desc}</p>{mono_html}</div>',
        unsafe_allow_html=True,
    )


def render_pipeline(animate: bool) -> None:
    """파이프라인 진행 로그 (연출 또는 최근 실행 로그 재표시).

    파일 업로드 검토는 run_live_review() 가 단계별 실호출 로그를 직접 그린다.
    이 함수는 (1) 파일 없이 실행한 mock 연출과 (2) 완료 화면에서 최근 로그
    재표시(세션의 live_steps 우선)에 쓰인다.
    """
    steps = st.session_state.get("live_steps") or PIPELINE_STEPS
    st.markdown("##### 파이프라인 진행 로그")
    with st.container(border=True):
        st.caption(
            "계약서 한 부가 결과로 나오기까지 실행되는 단계 — "
            + _badge("MCP 도구", "#DDEEFB;color:#2E6E9E")
            + _badge("내부 단계", "#F2F3FB;color:#5F6779"),
            unsafe_allow_html=True,
        )
        total = len(steps)
        for i, (is_tool, name, desc, mono) in enumerate(steps):
            _render_step(i + 1, is_tool, name, desc, mono, last=(i == total - 1))
            if animate:
                time.sleep(STEP_SEC)


def render_results(result: ReviewDemoResult) -> None:
    """검토 결과: LLM 요약 → 프레이밍 안내 → 요약 밴드 → 유형별 그룹(가로 나열)."""
    st.markdown("##### 검토 결과")
    source = st.session_state.get("data_source")
    if source:
        st.caption(f"데이터 출처: {source}")

    # LLM 근거 기반 요약 (검토 결과 바로 아래)
    summary = generate_llm_summary(result)
    st.markdown(
        '<div class="ws-llm">✨ <b>근거 기반 요약 — LLM (검출 결과만 인용)</b><br>'
        f"{summary}<br>"
        '<span style="font-size:11.5px;color:#8F94A8">요약은 검출 결과와 법령 조문만 입력받아 '
        "생성되며, 자체 법률 해석을 만들지 않습니다. 해석 고도화는 다음 프로젝트에서 진행 예정.</span></div>",
        unsafe_allow_html=True,
    )

    st.info("아래 결과는 **검토가 필요한 후보**를 표시한 것이며, 위법·불리함을 단정하지 않습니다.", icon="ℹ️")

    by_dev: dict[str, list[ClauseCard]] = {d: [] for d in DEVIATION_META}
    for card in result.cards:
        by_dev.setdefault(card.deviation, []).append(card)
    counts = {
        DEV_NONE: len(result.none_titles),
        **{d: len(cards) for d, cards in by_dev.items() if d != DEV_NONE},
    }

    # 요약 밴드 (카드 순서와 동일: NONE → CHANGED → MISSING → EXTRA → NO_MATCH)
    tiles = st.columns(5)
    for col, dev in zip(tiles, DEVIATION_META):
        _, _, style = DEVIATION_META[dev]
        sub = '<p class="sub">표준 기준</p>' if dev == DEV_MISSING else ""
        col.markdown(
            f'<div class="ws-tile" style="background:{style.split(";")[0]}">'
            f'<p class="lbl" style="{style.split(";")[1]}">{dev}</p>'
            f'<p class="val" style="{style.split(";")[1]}">{counts.get(dev, 0)}</p>{sub}</div>',
            unsafe_allow_html=True,
        )

    # 유형별 그룹: 가로 나열, 접힌 상태에서 시작
    groups = st.columns(5, gap="small")
    for col, dev in zip(groups, DEVIATION_META):
        dot, desc, _ = DEVIATION_META[dev]
        with col, st.expander(f"{dot} **{dev}** · {counts.get(dev, 0)}건", expanded=False):
            st.caption(desc)
            if dev == DEV_NONE:
                st.markdown(" · ".join(result.none_titles) if result.none_titles else "—")
                continue
            if not by_dev.get(dev):
                st.markdown("해당 없음")
                continue
            for card in by_dev[dev]:
                st.markdown(f"**{card.title}**")
                if card.confidence is not None and card.deviation != DEV_MISSING:
                    st.caption(f"신뢰도 {card.confidence:.2f}")
                if card.toxic_pattern:
                    st.error(f"독소 패턴 · {card.toxic_pattern}", icon="⚠️")
                if card.body_user and card.body_std:
                    st.markdown(f"*내 계약서*\n\n{card.body_user}")
                    st.markdown(f"*표준조항*\n\n{card.body_std}")
                elif card.body_user and card.deviation in (DEV_EXTRA, DEV_NO_MATCH):
                    st.markdown(f"*내 계약서*\n\n{_snippet(card.body_user, 150)}")
                if card.note:
                    st.markdown(card.note)
                for g in card.grounding:
                    st.caption(f"⚖️ 근거: {g.law_name} {g.article} ({g.source})")
                if card.std_ref:
                    st.caption(f"표준 출처: {card.std_ref}")
                st.divider()


def render_eval() -> None:
    """평가 · 개선: 설계·지표 → 측정 결과(ablation) → 개선 사이클."""
    st.markdown("##### 평가 · 개선")
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        st.markdown("**골든셋 설계 — 3가지 케이스 유형**")
        st.caption("가이드라인 테스트 유형과 1:1 대응 · 라벨링 진행 중")
        st.markdown(
            "- 정상 매칭 (정답이 문서에 있음)\n"
            "- 말바꿈 · 순서 뒤바뀜 (변형·함정)\n"
            "- 대응 없음 (문서에 없음 → **NO_MATCH가 정답**)"
        )
    with c2, st.container(border=True):
        st.markdown("**측정 지표 — LLM-judge 없이 전부 결정론적 계산**")
        st.caption("같은 골든셋에 다시 돌리면 같은 수치가 나오는, 재현 가능한 평가")
        st.markdown(
            "- Recall@k · MRR — 잘 찾는가\n"
            "- Precision / Recall (이탈·독소) — 제대로 짚는가\n"
            "- **특이도(Specificity)** — 없는 걸 없다고 하는가"
        )

    with st.container(border=True):
        st.markdown("**리트리벌 ablation — 측정 결과**")
        st.caption('"조항 몇십 개면 체크리스트로도 되지 않나"를 주장이 아닌 수치로 검증')
        metrics = load_ablation_metrics()
        variants = [
            ("bm25", "BM25-only (단어매칭)"),
            ("dense", "Dense-only (의미)"),
            ("hybrid", "하이브리드 (의미+단어)"),
            ("hybrid_rerank", "하이브리드 + 리랭커"),
        ]
        for key, label in variants:
            if metrics and key in metrics:
                st.progress(metrics[key], text=f"{label} — {metrics[key]:.3f}")
            else:
                st.progress(0.0, text=f"{label} — 측정 예정 (골든셋 확정 후 반영)")

    with st.container(border=True):
        st.markdown("**테스트 → 개선 사이클**")
        st.markdown(
            "1. **v1 측정** — 골든셋으로 검색·이탈·독소 탐지 지표 1차 측정\n"
            "2. **문제 발견** — 과탐 성향 확인: 정상 조항까지 검토 후보로 플래깅하는 경향을 특이도 지표로 포착\n"
            "3. **v2 개선** — 판정 임계값·매칭 로직 조정 후 같은 골든셋으로 재측정 (진행 중)"
        )


# ──────────────────────────────────────────────────────────────
# 메인 플로우: idle → running(로그 연출 + 실서버 호출) → done(결과가 위로 쌓임)
# ──────────────────────────────────────────────────────────────


def main() -> None:
    st.set_page_config(
        page_title="WorkShield — 프리랜서 계약서 검토",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",  # 데모 소개·연결 상태는 접힌 사이드바에
    )
    st.markdown(PALETTE_CSS, unsafe_allow_html=True)

    if "phase" not in st.session_state:
        st.session_state.phase = "idle"

    render_sidebar()
    st.caption("내부 시연용 · 사용자 서비스 화면 아님")
    st.title("WorkShield — 프리랜서 계약서 검토 서비스 데모")

    phase: str = st.session_state.phase

    if phase == "done":
        # 완료: 결과·평가가 맨 위, 로그가 그 아래, 검토 시작 카드는 맨 아래로 밀림
        render_results(st.session_state.result)
        st.divider()
        render_eval()
        st.divider()
        render_pipeline(animate=False)
        st.divider()
        render_form()

    elif phase == "running":
        # 재실행 가드: 검토 중 화면 조작으로 스크립트가 재시작돼도,
        # 이미 끝난 실행(job_token 일치)이면 다시 돌지 않고 결과로 직행
        token = st.session_state.get("job_token")
        if token is not None and st.session_state.get("done_token") == token:
            st.session_state.phase = "done"
            st.rerun()

        # 실행 중: 로그를 최상단에 단독 배치 → 단계가 하나씩 뜨는 것이 바로 보임
        st.caption("⏳ 검토 중 — 파이프라인이 순서대로 실행됩니다")
        file_bytes = st.session_state.get("upload_bytes")
        file_name = st.session_state.get("upload_name")
        contract_type = st.session_state.get("contract_type", "SW_FREELANCE")

        if file_bytes and file_name and st.session_state.get("live_log"):
            # 상세 모드(토글 켬): 단계별 실호출 로그 — 조항 수·매칭 점수가 실제 값 (느림)
            result, source = run_live_review(file_bytes, file_name, contract_type)
        else:
            # 빠른 모드(기본): 연출 로그 + review_contract 1회 호출 (파일 없으면 mock)
            st.session_state.live_steps = None
            render_pipeline(animate=True)
            with st.spinner("MCP 서버 검토 응답 대기 중… (전체 조항 배치 검색·재정렬)"):
                result, source = run_review_pipeline(file_bytes, file_name, contract_type)

        st.session_state.result = result
        st.session_state.data_source = source
        st.session_state.done_token = token
        st.session_state.phase = "done"
        time.sleep(0.8)  # 마지막 ✓ 단계가 눈에 들어올 여유
        st.rerun()

    else:  # idle
        render_form()

    st.caption("WorkShield 1차 MVP · 시연용 데모 (평가 수치는 골든셋 확정 후 반영)")


main()
