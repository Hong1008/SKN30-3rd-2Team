"""2차 LLM용 korean-law MCP 도구 프록시 등록기."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from adapter.korean_law_mcp import KoreanLawMCPClient


class KoreanLawWrapper:
    """주입된 MCP 앱에 외부 법률 도구 9개를 명시적으로 등록한다."""

    def __init__(self, mcp: FastMCP, client: KoreanLawMCPClient | None = None) -> None:
        self._client = client or KoreanLawMCPClient()
        mcp.add_tool(self.search_law, name="search_law")
        mcp.add_tool(self.get_law_text, name="get_law_text")
        mcp.add_tool(self.get_annexes, name="get_annexes")
        mcp.add_tool(self.legal_research, name="legal_research")
        mcp.add_tool(self.legal_analysis, name="legal_analysis")
        mcp.add_tool(self.discover_tools, name="discover_tools")
        mcp.add_tool(self.execute_tool, name="execute_tool")
        mcp.add_tool(self.search_decisions, name="search_decisions")
        mcp.add_tool(self.get_decision_text, name="get_decision_text")

    def search_law(self, query: str, display: int = 50) -> str:
        """법령명 키워드로 법령 식별자를 검색한다."""
        return self._client.search_law(query, display)

    def get_law_text(
        self, mst: str | None = None, law_id: str | None = None,
        jo: str | None = None, ef_yd: str | None = None,
    ) -> str:
        """법령 식별자와 선택 조문 코드로 조문 본문을 조회한다."""
        return self._client.get_law_text(mst=mst, law_id=law_id, jo=jo, ef_yd=ef_yd)

    def get_annexes(
        self, law_name: str, knd: str | None = None,
        byl_seq: str | None = None, annex_no: str | None = None,
    ) -> str:
        """법령의 별표 또는 서식을 조회한다."""
        return self._client.get_annexes(law_name, knd, byl_seq, annex_no)

    def legal_research(self, query: str, task: str = "full_research") -> str:
        """2차 검토용 다단계 법률 리서치를 수행한다."""
        return self._client.legal_research(query, task)

    def legal_analysis(self, mode: str, arguments: dict[str, Any] | None = None) -> str:
        """2차 검토용 인용 검증·행위시법 분석을 수행한다."""
        return self._client.legal_analysis(mode, **(arguments or {}))

    def discover_tools(self, intent: str) -> str:
        """외부 법률 MCP의 추가 도구를 탐색한다."""
        return self._client.discover_tools(intent)

    def execute_tool(self, tool_name: str, params: dict[str, Any]) -> str:
        """탐색한 외부 도구를 지정 인자로 실행한다."""
        return self._client.execute_tool(tool_name, params)

    def search_decisions(self, domain: str, query: str, options: dict[str, Any] | None = None) -> str:
        """판례·해석례 등 결정을 검색한다."""
        return self._client.search_decisions(domain, query, **(options or {}))

    def get_decision_text(self, domain: str, decision_id: str, full: bool | None = None) -> str:
        """결정 식별자로 전문을 조회한다."""
        return self._client.get_decision_text(domain, decision_id, full)
