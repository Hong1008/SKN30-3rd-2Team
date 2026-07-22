"""korean-law-mcp 장기 세션 lifecycle 계약 테스트."""

import asyncio
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

import pytest

from adapter.korean_law_mcp import KoreanLawMCPClient


def test_start는_앱_수명_중_한번만_연결하고_close에서_정상_종료한다():
    """동일 클라이언트는 owner 작업 하나를 재사용하고 종료 상태를 정리한다."""
    client = KoreanLawMCPClient()
    loop = MagicMock()
    loop.is_closed.return_value = False
    thread = MagicMock()
    owner_future = MagicMock()
    submitted = []

    client._ready.wait = MagicMock(return_value=True)  # type: ignore[method-assign]
    client._connected.wait = MagicMock(return_value=True)  # type: ignore[method-assign]

    def submit(coroutine):
        coroutine.close()
        submitted.append(coroutine)
        return owner_future

    client._submit = submit  # type: ignore[method-assign]

    with (
        patch("adapter.korean_law_mcp.asyncio.new_event_loop", return_value=loop),
        patch("adapter.korean_law_mcp.threading.Thread", return_value=thread),
    ):
        client.start()
        client.start()
        client.close()

    assert len(submitted) == 1
    thread.start.assert_called_once_with()
    owner_future.result.assert_called_once_with(timeout=10)
    thread.join.assert_called_once_with(timeout=10)
    assert client._loop is None
    assert client._thread is None


def test_한_세션의_동시_도구호출은_락으로_직렬화된다():
    """stdio 요청/응답 스트림은 한 번에 하나의 call_tool만 사용한다."""
    client = KoreanLawMCPClient()
    active = 0
    max_active = 0

    class Session:
        async def call_tool(self, _name, _arguments):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return type("Result", (), {"content": [type("Text", (), {"text": "ok"})()]})()

    async def run() -> list[str]:
        client._session = Session()  # type: ignore[assignment]
        client._call_lock = asyncio.Lock()
        return await asyncio.gather(
            client._call_mcp_tool("search_law", {"query": "민법"}),
            client._call_mcp_tool("search_law", {"query": "저작권법"}),
        )

    assert asyncio.run(run()) == ["ok", "ok"]
    assert max_active == 1


def test_외부_mcp_is_error_응답은_성공_문자열로_반환하지_않는다():
    """MCP 프로토콜 오류 결과의 텍스트를 정상 결과로 오인하지 않는다."""
    client = KoreanLawMCPClient()

    class Session:
        async def call_tool(self, _name, _arguments):
            return type(
                "Result",
                (),
                {
                    "isError": True,
                    "content": [type("Text", (), {"text": "upstream secret detail"})()],
                },
            )()

    async def run() -> str:
        client._session = Session()  # type: ignore[assignment]
        client._call_lock = asyncio.Lock()
        return await client._call_mcp_tool("search_law", {"query": "민법"})

    with pytest.raises(RuntimeError, match="오류 응답"):
        asyncio.run(run())


def test_외부_mcp_도구_호출은_설정된_시간_안에_끝나야_한다():
    """세션 연결 이후 실제 call_tool에도 읽기 제한시간을 적용한다."""
    client = KoreanLawMCPClient(call_timeout_seconds=0.01)

    class Session:
        async def call_tool(self, _name, _arguments):
            await asyncio.sleep(1)

    async def run() -> str:
        client._session = Session()  # type: ignore[assignment]
        client._call_lock = asyncio.Lock()
        return await client._call_mcp_tool("search_law", {"query": "민법"})

    with pytest.raises(TimeoutError):
        asyncio.run(run())


def test_공개_연동_오류는_내부_예외_원문을_노출하지_않는다():
    """실행 경로와 외부 서버의 상세 오류는 로그에만 남긴다."""
    client = KoreanLawMCPClient()
    failed: Future[str] = Future()
    failed.set_exception(RuntimeError("/private/path token=secret"))
    client.start = lambda: None  # type: ignore[method-assign]

    def submit(coroutine):
        coroutine.close()
        return failed

    client._submit = submit  # type: ignore[method-assign]

    with pytest.raises(RuntimeError) as raised:
        client._run_mcp_sync("search_law", {"query": "민법"})

    assert "search_law" in str(raised.value)
    assert "/private/path" not in str(raised.value)
    assert "secret" not in str(raised.value)
