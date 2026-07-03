"""OpenAI 호환 provider — openai SDK 하나로 openai/gemini/custom 처리.
사고과정 스트리밍(stream())만 provider별로 경로가 갈린다:
- openai: Responses API의 reasoning.summary 이벤트 (Chat Completions는 reasoning 텍스트를 반환하지 않음)
- gemini/custom: Chat Completions content에 섞여 나오는 <think>/<thought> 태그를 직접 분리
"""
import re

from .base import AssistantTurn, ProviderConfig, ToolCall
from openai import OpenAI

_THOUGHT_OPENERS = ("<thought>", "<think>")
_THOUGHT_RE = re.compile(r"<(thought|think)>.*?</\1>", re.DOTALL)


def _split_thought_tags(deltas):
    """<think>/<thought> 태그로 감싸인 content 델타 스트림을 (channel, text) 로 분리.
    태그가 여러 청크에 걸쳐 잘려 와도 안전하도록 경계를 버퍼링한다."""
    buf = ""
    started = False
    mode = "answer"
    closer = None
    for d in deltas:
        if not d:
            continue
        buf += d
        if not started:
            lead = buf.lstrip()
            if not lead:
                continue
            if any(op.startswith(lead) and len(lead) < len(op) for op in _THOUGHT_OPENERS):
                continue
            opener = next((op for op in _THOUGHT_OPENERS if lead.startswith(op)), None)
            if opener:
                mode = "thought"
                closer = opener.replace("<", "</", 1)
                buf = lead[len(opener):]
            else:
                mode = "answer"
                buf = lead
            started = True
        if mode == "thought":
            idx = buf.find(closer)
            if idx == -1:
                hold = len(closer) - 1
                if len(buf) > hold:
                    yield ("thought", buf[:-hold])
                    buf = buf[-hold:]
            else:
                if idx:
                    yield ("thought", buf[:idx])
                buf = buf[idx + len(closer):]
                mode = "answer"
                if buf:
                    yield ("answer", buf)
                    buf = ""
        else:
            if buf:
                yield ("answer", buf)
                buf = ""
    if buf:
        yield (mode, buf)


class OpenAICompatProvider:
    """base_url 만 바꿔 OpenAI·Gemini(OpenAI 호환)·자체 vLLM 서빙을 동일 코드로 호출."""

    def __init__(self, config: ProviderConfig):
        if not config.model:
            raise ValueError(f"[{config.name}] 모델명이 비어 있습니다 — 환경변수(*_MODEL)를 확인하세요.")
        self.config = config
        kwargs = {}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = OpenAI(**kwargs)

    def complete(self, messages, tools=None, temperature=0.2) -> AssistantTurn:
        params = {"model": self.config.model, "messages": messages, "temperature": temperature}
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        resp = self._client.chat.completions.create(**params)
        msg = resp.choices[0].message
        calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
            for tc in (msg.tool_calls or [])
        ]
        return AssistantTurn(content=msg.content, tool_calls=calls, raw=msg)

    def parse(self, messages, response_format, temperature=0.2):
        """구조화 출력(response_format=pydantic 모델)으로 강제 호출.
        gemini/custom 백엔드가 strict json_schema를 지원하지 않으면 parsed 가 None일 수 있음."""
        completion = self._client.chat.completions.parse(
            model=self.config.model, messages=messages,
            response_format=response_format, temperature=temperature,
        )
        return completion.choices[0].message.parsed

    def stream(self, messages, temperature=0.2):
        """(channel, delta) 를 순차 yield. channel ∈ {"thought", "answer"} (요약 스트리밍용, 도구 미사용)."""
        if self.config.name == "openai" and self.config.reasoning_effort:
            yield from self._stream_openai_reasoning(messages, temperature)
        else:
            yield from _split_thought_tags(self._stream_content(messages, temperature))

    def _stream_content(self, messages, temperature):
        """Chat Completions content 델타만 순차 yield (내부용)."""
        resp = self._client.chat.completions.create(
            model=self.config.model, messages=messages, temperature=temperature, stream=True,
        )
        for chunk in resp:
            if not chunk.choices:
                continue
            piece = getattr(chunk.choices[0].delta, "content", None)
            if piece:
                yield piece

    def _stream_openai_reasoning(self, messages, temperature):
        """Responses API로 사고과정(reasoning.summary)과 본문을 각각 별도 이벤트로 받아 (channel, delta) 로 변환.
        reasoning 계열 모델은 커스텀 temperature를 거부하는 경우가 많아 전달하지 않음(API 기본값 사용)."""
        stream = self._client.responses.create(
            model=self.config.model, input=messages, stream=True,
            reasoning={"effort": self.config.reasoning_effort, "summary": self.config.reasoning_summary},
        )
        for event in stream:
            if event.type == "response.reasoning_summary_text.delta":
                yield ("thought", event.delta)
            elif event.type == "response.output_text.delta":
                yield ("answer", event.delta)
