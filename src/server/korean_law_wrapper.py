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
        """법령명 키워드로 lawId·mst 식별자를 검색합니다.

        법령명만 알고 식별자를 모를 때 먼저 사용하고, 특정 조문 본문은 결과의 lawId 또는
        mst를 get_law_text에 넘겨 조회하세요. query는 법령명·약칭이고 display는 최대
        결과 수(기본 50)입니다.

        반환값은 FastMCP 출력의 result 필드에 담긴 외부 MCP의 직렬화된 문자열입니다.
        검색 결과는 식별자 후보이며 위법·합법, 유불리, 승소 가능성을 단정하지 않습니다.
        빈 결과는 정확한 법령명으로 재검색해야 하며, 연동 오류는 예외로 반환됩니다.
        """
        return self._client.search_law(query, display)

    def get_law_text(
        self, mst: str | None = None, law_id: str | None = None,
        jo: str | None = None, ef_yd: str | None = None,
    ) -> str:
        """법령 식별자와 선택 조문으로 법령 본문을 조회합니다.

        mst 또는 law_id 중 하나는 반드시 필요하며 search_law 결과에서 얻습니다. jo는
        "제38조" 또는 6자리 코드 "003800"을 받고, ef_yd는 시행일 YYYYMMDD입니다.
        jo를 생략하면 법령 전체를 조회하므로 특정 조문만 필요하면 반드시 지정하세요.

        반환값은 result 필드의 직렬화된 법령 본문 문자열입니다. 조문 본문은 참고 근거이며
        특정 계약에 대한 위법·합법, 유불리, 승소 가능성을 단정하지 않습니다.
        빈 결과와 연동 오류는 정상 본문으로 숨기지 않고 예외로 반환됩니다.
        """
        if mst is None and law_id is None:
            raise ValueError("mst 또는 law_id 중 하나를 지정해야 합니다.")
        return self._client.get_law_text(mst=mst, law_id=law_id, jo=jo, ef_yd=ef_yd)

    def get_annexes(
        self, law_name: str, knd: str | None = None,
        byl_seq: str | None = None, annex_no: str | None = None,
    ) -> str:
        """법령의 별표·서식에 있는 금액, 기준, 양식 내용을 조회합니다.

        law_name은 필수 법령명입니다. knd는 1=별표, 2=서식, 3=부칙별표, 4=부칙서식,
        5=전체이며, byl_seq는 6자리 별표 일련번호, annex_no는 "4"·"별표4"·"제4호" 형식의
        대체 입력입니다. 조문 본문은 get_law_text를 사용하세요.

        반환값은 result 필드의 직렬화된 별표·서식 문자열입니다. 자료는 참고 근거이며
        특정 계약에 대한 위법·합법, 유불리, 승소 가능성을 단정하지 않습니다.
        빈 결과와 연동 오류는 예외로 반환됩니다.
        """
        return self._client.get_annexes(law_name, knd, byl_seq, annex_no)

    def legal_research(self, query: str, task: str = "full_research") -> str:
        """단일 조회로 답하기 어려운 2차 다단계 법률 리서치를 수행합니다.

        task는 full_research(종합), law_system(법체계), action_basis(처분·허가 근거),
        dispute_prep(불복·소송), amendment_track(개정 이력), ordinance_compare(조례 비교),
        procedure_detail(절차·수수료·서식) 중 선택합니다. 현재 프록시의 query·task 인자로
        실행할 수 없는 document_review(text 필수)는 discover_tools 후 execute_tool로 호출하세요.
        법령 식별자나 조문을 알고 있는 단일 조회는 search_law/get_law_text가 적합합니다.

        반환값은 result 필드의 직렬화된 리서치 문자열입니다. 반드시 원문 조문·판례를
        재확인해야 하며 위법·합법, 유불리, 승소 가능성을 단정하지 않습니다.
        빈 결과와 연동 오류는 예외로 반환됩니다.
        """
        return self._client.legal_research(query, task)

    def legal_analysis(self, mode: str, arguments: dict[str, Any] | None = None) -> str:
        """2차 검토에서 인용·판례 상태·행위시법·영향 관계를 검증합니다.

        mode별 arguments 필수 키는 verify_citations={text}, cite_check={caseNumber},
        applicable_law={lawName,date}, impact_map={lawName,jo}입니다. applicable_law의 jo는 선택입니다.
        인용 실존 검증은 verify_citations, 판례 변경·폐기 후속 확인은 cite_check,
        특정 날짜의 시행법령은 applicable_law, 조문 인용 그래프는 impact_map을 선택하세요.

        반환값은 result 필드의 직렬화된 분석 문자열입니다. 검증 결과도 특정 사안의
        위법·합법, 유불리, 승소 가능성을 단정하지 않습니다. 빈 결과와 연동 오류는
        예외로 반환됩니다.
        """
        return self._client.legal_analysis(mode, **(arguments or {}))

    def discover_tools(self, intent: str) -> str:
        """기본 9개 도구로 처리하기 어려운 의도에 맞는 80개 이상의 전문 도구를 탐색합니다.

        intent에 "공정위", "헌재", "조세심판", "조약", "법률용어" 같은 목적을 넣습니다.
        결과에서 도구명과 인자 스키마를 확인한 뒤 execute_tool로 실행하세요.

        반환값은 result 필드의 직렬화된 도구 후보 문자열입니다. 도구 후보는 법률 판단이 아니며
        위법·합법, 유불리, 승소 가능성을 단정하지 않습니다. 빈 결과와 연동 오류는
        예외로 반환됩니다.
        """
        return self._client.discover_tools(intent)

    def execute_tool(self, tool_name: str, params: dict[str, Any]) -> str:
        """discover_tools로 확인한 외부 전문 도구를 프록시 실행합니다.

        tool_name은 discover_tools가 반환한 정확한 도구명이고 params는 그 도구의 스키마에
        맞는 인자 객체입니다. 이 도구는 임의 인자를 보정하지 않으므로 반드시 탐색 결과를
        먼저 확인하세요.

        반환값은 result 필드의 직렬화된 외부 도구 문자열입니다. 결과는 참고 자료이며
        위법·합법, 유불리, 승소 가능성을 단정하지 않습니다. 빈 결과와 연동 오류는
        예외로 반환됩니다.
        """
        return self._client.execute_tool(tool_name, params)

    def search_decisions(self, domain: str, query: str, options: dict[str, Any] | None = None) -> str:
        """판례·해석례·헌재·행심 등 18개 도메인의 결정 목록을 검색합니다.

        domain은 precedent, interpretation, tax_tribunal, customs, nts, constitutional,
        admin_appeal, ftc, pipc, nlrc, acr, appeal_review, acr_special, school, public_corp,
        public_inst, treaty, english_law 중 하나입니다. 일반 판례는 precedent, 국세청
        직접 회신은 nts를 사용하세요. query는 검색어입니다.

        options는 외부 도구에 펼쳐 전달할 display, page, sort, options 키를 담습니다.
        예를 들어 판례 본문을 함께 받으려면
        {"display": 10, "options": {"includeText": true, "detailLimit": 3}}을 사용합니다.
        검색 결과는 목록이므로 전문이 필요하면 결과 ID를 get_decision_text에 넘기세요.

        반환값은 result 필드의 직렬화된 검색 문자열입니다. 검색 결과는 법률 판단이 아니며
        위법·합법, 유불리, 승소 가능성을 단정하지 않습니다. 빈 결과와 연동 오류는
        예외로 반환됩니다.
        """
        return self._client.search_decisions(domain, query, **(options or {}))

    def get_decision_text(self, domain: str, decision_id: str, full: bool | None = None) -> str:
        """search_decisions에서 얻은 결정 식별자로 본문을 조회합니다.

        domain은 검색할 때 사용한 18개 도메인 값과 같아야 하고 decision_id는 검색 결과의
        ID입니다. full=true는 본문 전문을, false 또는 생략은 이유·전문 섹션을 계단식으로
        축약한 결과를 요청합니다. 우선 탐색이 필요하면 search_decisions를 먼저 사용하세요.

        반환값은 result 필드의 직렬화된 결정 본문 문자열입니다. 요약된 본문이면 중요한
        판단 전에 full=true로 원문을 재확인하세요. 반환값은 특정 사안의 위법·합법,
        유불리, 승소 가능성을 단정하지 않습니다. 빈 결과와 연동 오류는 예외로 반환됩니다.
        """
        return self._client.get_decision_text(domain, decision_id, full)
