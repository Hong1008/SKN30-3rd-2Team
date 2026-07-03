"""요약(도구 없음) + 대화형 에이전트(MCP 도구 루프)."""
import asyncio
import json
import re
from typing import Optional

from workshield_mcp_client import WorkShieldMCPClient

from .base import AssistantTurn
from .mcp_tools import execute_tool_call, load_openai_tools
from .prompts import AGENT_SYSTEM, SUMMARY_SYSTEM
from .registry import build_provider
from .schemas import StructuredSummary

_MCP_READ_TIMEOUT = 300

_THOUGHT_RE = re.compile(r"<(thought|think)>.*?</\1>", re.DOTALL)


def _strip_thought(text: str) -> str:
    """비스트리밍 경로에서 사고과정 블록 제거."""
    return _THOUGHT_RE.sub("", text or "").strip()


def _summary_messages(payload: dict) -> list[dict]:
    user = (
        "다음은 WorkShield 파이프라인의 검출 결과(JSON)입니다. 이 결과와 그 안의 법령 조문만을 "
        "근거로, 한국어 3~5문장 요약을 작성하세요.\n"
        "- payload의 'matched_no_review' 목록은 '표준과 일치하여 검토가 불필요한' 조항입니다. "
        "이를 'NO_MATCH(근거를 찾지 못해 판단하지 않음)'와 절대 혼동하지 마세요.\n"
        "- detections 의 deviation 이 'NO_MATCH' 인 항목만 '근거를 찾지 못해 판단하지 않았다'고 표현하세요.\n"
        "- 근거가 없는 항목은 지어내지 말고 판단하지 마세요.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return [{"role": "system", "content": SUMMARY_SYSTEM}, {"role": "user", "content": user}]


def summarize(payload: dict, provider=None) -> StructuredSummary:
    """검출 결과+법령만 근거로 구조화 요약 (도구 없음, 비스트리밍).
    response_format=StructuredSummary 로 강제 — gemini/custom 백엔드가 strict json_schema를
    지원하지 않아 파싱에 실패하면 RuntimeError (빈 응답 반환 금지)."""
    prov = provider or build_provider()
    parsed = prov.parse(_summary_messages(payload), response_format=StructuredSummary, temperature=0.2)
    if parsed is None:
        raise RuntimeError(f"[{prov.config.name}] 구조화 요약 파싱 실패 — 모델이 스키마를 준수하지 않았습니다.")
    return parsed


def summarize_stream(payload: dict, provider=None):
    """summarize 의 스트리밍 버전 — (channel, delta) 를 순차 yield. channel ∈ {'thought','answer'}.
    태그 파싱(gemini/custom) vs Responses API reasoning(openai) 분기는 provider.stream() 내부에서 처리."""
    prov = provider or build_provider()
    yield from prov.stream(_summary_messages(payload), temperature=0.2)


def _assistant_message(turn: AssistantTurn) -> dict:
    msg: dict = {"role": "assistant", "content": turn.content or ""}
    if turn.tool_calls:
        msg["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in turn.tool_calls
        ]
    return msg


class WorkShieldAgent:
    """WorkShield MCP 도구를 스스로 호출하는 대화형 에이전트 (provider 무관 도구 루프)."""

    def __init__(self, provider=None, max_steps: int = 6):
        self.provider = provider or build_provider()
        self.max_steps = max_steps

    async def _run_async(self, user_message: str, contract_type: Optional[str] = None) -> str:
        async with WorkShieldMCPClient(read_timeout=_MCP_READ_TIMEOUT) as client:
            tools = await load_openai_tools(client)
            messages = [{"role": "system", "content": AGENT_SYSTEM}]
            if contract_type:
                messages.append({"role": "system", "content": f"현재 contract_type={contract_type}"})
            messages.append({"role": "user", "content": user_message})

            for _ in range(self.max_steps):
                turn = self.provider.complete(messages, tools=tools, temperature=0.1)
                messages.append(_assistant_message(turn))
                if not turn.tool_calls:
                    return _strip_thought(turn.content or "")
                for tc in turn.tool_calls:
                    result = await execute_tool_call(client, tc.name, tc.arguments)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            final = self.provider.complete(
                messages + [{"role": "user",
                             "content": "지금까지의 도구 결과만으로 최종 답변을 정리하세요. 근거 없는 항목은 판단하지 마세요."}],
                tools=None, temperature=0.1,
            )
            return _strip_thought(final.content or "")

    def ask(self, user_message: str, contract_type: Optional[str] = None) -> str:
        return asyncio.run(self._run_async(user_message, contract_type))


def invoke_workshield(user_message: str, contract_type: Optional[str] = None) -> str:
    """[하위호환] 기존 llm.invoke_workshield 대체."""
    return WorkShieldAgent().ask(user_message, contract_type)
