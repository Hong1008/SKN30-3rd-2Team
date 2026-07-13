"""korean-law-mcp와 통신하는 어댑터.

1차 grounding은 법령명 정확 일치와 조문 조회만 사용한다. AI 기반 리서치 도구는
2차 MCP 표면에서만 별도로 노출한다.
"""

import json
import logging
import re
import asyncio
import threading
from collections.abc import Coroutine
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class KoreanLawMCPClient:
    """외부 korean-law MCP의 도구를 동기식 Python 메서드로 매핑한다.

    stdio 서버와 ``ClientSession``은 전용 이벤트 루프 스레드에 한 번만 연결한다.
    따라서 korean-law-mcp가 가진 프로세스 내 TTL 캐시는 WorkShield 프로세스가
    살아 있는 동안 유지된다. 동기 MCP 도구 호출은 이 전용 루프에 제출되므로,
    FastMCP의 이벤트 루프를 재진입하거나 막지 않는다.
    """

    def __init__(self) -> None:
        self._state_lock = threading.RLock()
        self._ready = threading.Event()
        self._connected = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._owner_future: Any | None = None
        self._close_signal: asyncio.Event | None = None
        self._startup_error: BaseException | None = None
        self._session: ClientSession | None = None
        self._call_lock: asyncio.Lock | None = None

    def start(self) -> None:
        """외부 MCP 자식 프로세스와 세션을 시작한다(여러 번 호출해도 안전)."""
        with self._state_lock:
            if self._loop is None:
                self._ready.clear()
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=self._run_loop,
                    args=(loop,),
                    name="korean-law-mcp-loop",
                    daemon=True,
                )
                self._loop = loop
                self._thread = thread
                thread.start()
                if not self._ready.wait(timeout=10):
                    self._loop = None
                    self._thread = None
                    raise RuntimeError("korean-law MCP 전용 이벤트 루프를 시작하지 못했습니다.")

            if self._owner_future is None:
                self._connected.clear()
                self._startup_error = None
                self._owner_future = self._submit(self._own_session())
                if not self._connected.wait(timeout=10):
                    self.close()
                    raise RuntimeError("korean-law MCP 세션 연결 시간이 초과되었습니다.")
                if self._startup_error is not None:
                    error = self._startup_error
                    self.close()
                    raise RuntimeError(f"korean-law MCP 세션 연결 실패: {error}") from error

    def close(self) -> None:
        """세션과 자식 프로세스를 종료한다(여러 번 호출해도 안전)."""
        with self._state_lock:
            loop, thread = self._loop, self._thread
            if loop is None or thread is None:
                return
            owner_future, close_signal = self._owner_future, self._close_signal
            try:
                if close_signal is not None:
                    loop.call_soon_threadsafe(close_signal.set)
                if owner_future is not None:
                    owner_future.result(timeout=10)
            finally:
                loop.call_soon_threadsafe(loop.stop)
                thread.join(timeout=10)
                self._loop = None
                self._thread = None
                self._session = None
                self._call_lock = None
                self._owner_future = None
                self._close_signal = None
                self._startup_error = None
                self._connected.clear()

    def _run_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """전용 이벤트 루프를 실행한다."""
        asyncio.set_event_loop(loop)
        self._ready.set()
        loop.run_forever()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    def _submit(self, coroutine: Coroutine[Any, Any, Any]):
        """전용 루프에 코루틴을 제출한다."""
        loop = self._loop
        if loop is None or loop.is_closed():
            raise RuntimeError("korean-law MCP 세션이 시작되지 않았습니다.")
        return asyncio.run_coroutine_threadsafe(coroutine, loop)

    async def _own_session(self) -> None:
        """stdio 컨텍스트를 연 Task가 종료까지 소유한다.

        AnyIO의 cancel scope는 ``__aenter__``/``__aexit__``가 동일 Task에서 실행되어야
        한다. 따라서 호출 Task마다 context manager를 열고 닫지 않고, 이 owner Task가
        앱 수명 전체에서 ``AsyncExitStack``을 유지한다.
        """
        self._close_signal = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                params = StdioServerParameters(command="korean-law-mcp", args=[])
                read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await session.initialize()
                self._session = session
                self._call_lock = asyncio.Lock()
                self._connected.set()
                await self._close_signal.wait()
        except BaseException as error:
            self._startup_error = error
            self._connected.set()
            raise
        finally:
            self._session = None
            self._call_lock = None

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """이미 연결된 stdio MCP 서버의 도구를 호출하고 텍스트 결과를 반환한다."""
        if self._session is None or self._call_lock is None:
            raise RuntimeError("korean-law MCP 세션이 연결되지 않았습니다.")
        # ClientSession의 요청/응답 스트림을 한 세션에서 안전하게 재사용한다.
        async with self._call_lock:
            result = await self._session.call_tool(tool_name, arguments)
        if not result.content:
            raise RuntimeError(f"korean-law MCP 도구 '{tool_name}'의 결과가 비어 있습니다.")
        texts = [item.text for item in result.content if hasattr(item, "text")]
        if not texts:
            raise RuntimeError(f"korean-law MCP 도구 '{tool_name}'의 텍스트 결과가 없습니다.")
        return "\n".join(texts)

    def _run_mcp_sync(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """비동기 MCP 호출을 동기식 호출자로 안전하게 연결한다."""
        try:
            self.start()
            return self._submit(self._call_mcp_tool(tool_name, arguments)).result()
        except Exception as e:
            logging.error("korean-law MCP 도구 '%s' 호출 실패: %s", tool_name, e)
            raise RuntimeError(f"korean-law MCP 연동 오류 ({tool_name}): {e}") from e

    # 외부 서버에 공개된 9개 도구의 직접 매핑
    def search_law(self, query: str, display: int = 50) -> str:
        return self._run_mcp_sync("search_law", {"query": query, "display": display})

    def get_law_text(
        self,
        mst: str | None = None,
        law_id: str | None = None,
        jo: str | None = None,
        ef_yd: str | None = None,
    ) -> str:
        args = {"mst": mst, "lawId": law_id, "jo": jo, "efYd": ef_yd}
        return self._run_mcp_sync("get_law_text", {key: value for key, value in args.items() if value is not None})

    def get_annexes(
        self,
        law_name: str,
        knd: str | None = None,
        byl_seq: str | None = None,
        annex_no: str | None = None,
    ) -> str:
        args = {"lawName": law_name, "knd": knd, "bylSeq": byl_seq, "annexNo": annex_no}
        return self._run_mcp_sync("get_annexes", {key: value for key, value in args.items() if value is not None})

    def legal_research(self, query: str, task: str = "full_research") -> str:
        return self._run_mcp_sync("legal_research", {"query": query, "task": task})

    def legal_analysis(self, mode: str, **kwargs: Any) -> str:
        return self._run_mcp_sync("legal_analysis", {"mode": mode, **kwargs})

    def discover_tools(self, intent: str) -> str:
        return self._run_mcp_sync("discover_tools", {"intent": intent})

    def execute_tool(self, tool_name: str, params: dict[str, Any]) -> str:
        return self._run_mcp_sync("execute_tool", {"tool_name": tool_name, "params": params})

    def search_decisions(self, domain: str, query: str, **kwargs: Any) -> str:
        args = {"query": query, "domain": domain, **kwargs}
        return self._run_mcp_sync("search_decisions", {key: value for key, value in args.items() if value is not None})

    def get_decision_text(self, domain: str, decision_id: str, full: bool | None = None) -> str:
        args = {"id": decision_id, "domain": domain, "full": full}
        return self._run_mcp_sync("get_decision_text", {key: value for key, value in args.items() if value is not None})

    @staticmethod
    def _law_name(query: str) -> str | None:
        """카테고리 쿼리 앞부분에서 법령명을 추출한다."""
        match = re.match(r"\s*(.+?(?:법률|법))(?=\s|제|$)", query)
        return match.group(1) if match else None

    @staticmethod
    def _jo_code(query: str) -> str | None:
        """제N조의M 표기를 외부 도구가 요구하는 6자리 jo 코드로 변환한다."""
        match = re.search(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?", query)
        if not match:
            return None
        return f"{int(match.group(1)):04d}{int(match.group(2) or 0):02d}"

    @staticmethod
    def _exact_law_id(raw: str, law_name: str) -> tuple[str | None, str | None]:
        """검색 JSON에서 정확히 같은 법령명의 mst/lawId만 찾는다.

        부분 일치 결과는 1차에서 사용하지 않는다. JSON이 아닌 응답은 식별자를
        신뢰성 있게 판별할 수 없으므로 실패로 처리한다.
        """
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # korean-law-mcp 기본 응답은 사람이 읽는 텍스트다.
            # 각 결과 블록의 법령명과 식별자를 함께 읽어 정확 일치만 채택한다.
            pattern = re.compile(
                r"(?m)^\s*\d+\.\s*(?P<name>.+?)\s*\[[^\]]+\]"
                r"(?P<details>.*?)(?=^\s*\d+\.\s|\Z)",
                re.DOTALL,
            )
            for match in pattern.finditer(raw):
                if match.group("name").strip() != law_name:
                    continue
                details = match.group("details")
                mst_match = re.search(r"MST:\s*(\S+)", details)
                law_id_match = re.search(r"법령ID:\s*(\S+)", details)
                return (
                    mst_match.group(1) if mst_match else None,
                    law_id_match.group(1) if law_id_match else None,
                )
            return None, None

        def walk(value: Any):
            if isinstance(value, dict):
                name = value.get("lawName") or value.get("법령명") or value.get("name")
                if isinstance(name, str) and name.strip() == law_name:
                    yield value
                for child in value.values():
                    yield from walk(child)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)

        for item in walk(payload):
            mst = item.get("mst")
            law_id = item.get("lawId") or item.get("law_id")
            if mst or law_id:
                return (str(mst) if mst else None, str(law_id) if law_id else None)
        return None, None

    def query(self, query_str: str) -> str:
        """1차 grounding용 결정론적 체인: 정확 법령명 검색 후 해당 조문만 조회한다.

        법령명이 정확히 일치하지 않거나 식별자가 없으면 빈 문자열을 반환한다. 이는
        Grounder가 ``NO_RESULT``로 변환할 수 있는 명시적 '검색 결과 없음' 표식이다.
        외부 연결 실패는 예외로 전파한다.
        """
        law_name = self._law_name(query_str)
        if law_name is None:
            return ""
        mst, law_id = self._exact_law_id(self.search_law(law_name), law_name)
        if mst is None and law_id is None:
            return ""
        return self.get_law_text(mst=mst, law_id=law_id, jo=self._jo_code(query_str))


koreanLaw = KoreanLawMCPClient()
