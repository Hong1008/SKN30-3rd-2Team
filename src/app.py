"""WorkShield MCP 애플리케이션 조립 및 실행 진입점."""

import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from adapter.korean_law_mcp import koreanLaw
from server.korean_law_wrapper import KoreanLawWrapper
from server.server import WorkShieldTools


@asynccontextmanager
async def _lifespan(_app: FastMCP) -> AsyncIterator[dict[str, object]]:
    """외부 법률 MCP 세션을 앱 수명과 함께 열고 닫는다."""
    koreanLaw.start()
    try:
        yield {}
    finally:
        koreanLaw.close()


def create_app() -> FastMCP:
    """새 MCP 서버 인스턴스를 만들고 모든 도구·리소스를 등록한다."""
    mcp = FastMCP("WorkShield", lifespan=_lifespan)
    WorkShieldTools(mcp)
    # 1차 Grounder와 2차 프록시가 동일한 자식 프로세스/세션/TTL 캐시를 재사용한다.
    KoreanLawWrapper(mcp, client=koreanLaw)
    return mcp


def main() -> None:
    """환경 설정에 맞춰 조립된 MCP 서버를 실행한다."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] [%(levelname)s] (%(filename)s:%(lineno)d) %(message)s",
    )
    mcp = create_app()
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        mcp.settings.host = os.getenv("MCP_HOST", mcp.settings.host)
        mcp.settings.port = int(os.getenv("MCP_PORT", mcp.settings.port))
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
