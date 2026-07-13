"""korean-law-mcp 장기 세션 lifecycle 계약 테스트."""

import asyncio
from unittest.mock import AsyncMock

from adapter.korean_law_mcp import KoreanLawMCPClient


def test_start는_앱_수명_중_한번만_연결하고_close에서_정상_종료한다():
    """동일 클라이언트는 자식 프로세스/세션 하나를 재사용한다."""
    client = KoreanLawMCPClient()

    async def own_session() -> None:
        client._session = object()  # type: ignore[assignment]
        client._call_lock = asyncio.Lock()
        client._close_signal = asyncio.Event()
        client._connected.set()
        await client._close_signal.wait()

    client._own_session = AsyncMock(side_effect=own_session)  # type: ignore[method-assign]

    try:
        client.start()
        client.start()
        assert client._own_session.await_count == 1
    finally:
        client.close()

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
