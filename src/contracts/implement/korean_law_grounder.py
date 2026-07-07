import re
from typing import List, Optional

from contracts.ports import Grounder
from contracts.enums import Category, ContractType, ToxicPattern
from contracts.models import GroundingLaw
from adapter import koreanLaw

# 계약 카테고리와 매칭되는 국가 법제처 표준 검색어 정의
CATEGORY_QUERIES = {
    Category.PAYMENT: "민법 제665조 보수의 지급시기",
    Category.IP_OWNERSHIP: "저작권법 제10조 및 지식재산권 귀속",
    Category.SCOPE_SOW: "민법 제664조 도급의 의의",
    Category.TERMINATION: "민법 제673조 완성전의 도급인의 해제권",
    Category.CONFIDENTIALITY: "부정경쟁방지 및 영업비밀보호에 관한 법률 제2조 영업비밀",
    Category.LIABILITY: "민법 제390조 채무불이행과 손해배상",
    Category.DISPUTE: "민사소송법 제29조 합의관할",
    Category.WORKING_HOURS: "근로기준법 제50조 근로시간",
    Category.HOLIDAY_LEAVE: "근로기준법 제60조 연차 유급휴가",
    Category.SOCIAL_INSURANCE: "고용보험법 및 국민건강보험법 사회보험",
    # 민법 667조(수급인의 담보책임) — 도급 일반에 적용되는 하자담보 조문. korean-law-mcp로 실측 확인.
    Category.WARRANTY: "민법 제667조 수급인의 담보책임",
    # 산업안전보건법 63조(도급인의 안전조치·보건조치) — SI/SM·SW_EMPLOYMENT에서만 유효한 카테고리
    # (Category.contract_types 참조). korean-law-mcp로 실측 확인.
    Category.INDUSTRIAL_SAFETY: "산업안전보건법 제63조 도급인의 안전조치 및 보건조치",
    # 정보통신망법 45조(정보통신망의 안정성 확보 등) — SM_SUBCONTRACT 전용 카테고리. 실측 확인.
    Category.INFO_SECURITY: "정보통신망 이용촉진 및 정보보호 등에 관한 법률 제45조 정보통신망의 안정성 확보 등",
}

# SI/SM(하도급) 전용 오버라이드 — 카테고리는 SW_FREELANCE와 같아도 적용 법령이 다른 경우만 여기 추가.
# get_grounding 에서 (category, contract_type)로 여기부터 먼저 조회하고, 없으면 CATEGORY_QUERIES(공용)로
# 폴백한다. SI_SUBCONTRACT·SM_SUBCONTRACT는 둘 다 하도급법 적용 대상이라 값을 공유한다.
# (근거: docs/tasks/O_grounding_contract_type.md — 나머지 미매핑 카테고리는 법률 검토 후 추가)
_SUBCONTRACT_TYPES = frozenset({ContractType.SI_SUBCONTRACT, ContractType.SM_SUBCONTRACT})

SUBCONTRACT_CATEGORY_QUERIES = {
    Category.PAYMENT: "하도급거래 공정화에 관한 법률 제13조 하도급대금의 지급 등",
    Category.DELIVERY_INSPECTION: "하도급거래 공정화에 관한 법률 제9조 검사의 기준 방법 및 시기",
    Category.CONFIDENTIALITY: "하도급거래 공정화에 관한 법률 제12조의3 기술자료 제공 요구 금지 등",
    # 하도급법 8조(부당한 위탁취소의 금지 등) — SI/SM 표준계약서의 "부당한 위탁취소 등의 금지" 조항과
    # 정확히 일치. 민법 673조(도급인의 임의해제권)와는 반대로 "원사업자의 부당 취소로부터 수급사업자를
    # 보호"하는 하도급법 특유 조문이라 SW_FREELANCE(민법 673조)와 분리. korean-law-mcp로 실측 확인.
    Category.TERMINATION: "하도급거래 공정화에 관한 법률 제8조 부당한 위탁취소의 금지 등",
    # 하도급법 35조(손해배상 책임) — 위반행위 손해의 최대 3~5배까지 배상하는 하도급법 특유 가중책임
    # 조항. 민법 390조(일반 채무불이행 손배)와는 별개 근거. korean-law-mcp로 실측 확인.
    Category.LIABILITY: "하도급거래 공정화에 관한 법률 제35조 손해배상 책임",
}

TOXIC_QUERIES = {
    ToxicPattern.NONCOMPETE_EXCESS: "민법 제103조 반사회질서의 법률행위",
    ToxicPattern.IP_TOTAL_FREE: "저작권법 제45조 저작재산권의 양도",
    ToxicPattern.PAYMENT_DELAY_UNFAIR: "하도급거래 공정화에 관한 법률 제13조 하도급대금의 지급",
    ToxicPattern.UNILATERAL_CHANGE: "약관의 규제에 관한 법률 제10조 채무의 이행",
    ToxicPattern.UNFAIR_DAMAGE_CLAIM: "약관의 규제에 관한 법률 제8조 손해배상액의 예정",
    ToxicPattern.UNILATERAL_INTERPRETATION: "약관의 규제에 관한 법률 제5조 약관의 해석",
    ToxicPattern.UNILATERAL_CANCELLATION: "약관의 규제에 관한 법률 제9조 계약의 해제 해지",
    ToxicPattern.INDEFINITE_CONFIDENTIALITY: "부정경쟁방지 및 영업비밀보호에 관한 법률 제2조 영업비밀",
    ToxicPattern.UNPAID_ADDITIONAL_WORK: "하도급거래 공정화에 관한 법률 제3조의4 부당한 특약의 금지",
}

class KoreanLawGrounder(Grounder):
    """
    korean-law MCP 클라이언트 어댑터를 사용하여, 특정 계약서 분류(Category) 또는
    본문 내용에 부합하는 근거 법조문을 수집하는 Grounder 포트 구현체입니다.
    """

    def _parse_raw_text_to_laws(self, query_str: str, raw_text: str) -> List[GroundingLaw]:
        """조회된 줄글 형태의 법령 정보 텍스트를 구조화된 GroundingLaw 리스트로 가공합니다."""
        # 1. 쿼리 키워드에서 기본 법령 이름 유추 (예: '저작권법 제10조' -> '저작권법')
        law_name_match = re.search(r"([가-힣]+법)", query_str)
        fallback_law_name = law_name_match.group(1) if law_name_match else "관련 법령"

        # 2. 본문에서 조항 단위 헤더 매칭 (예: '### 제5조(저작물)' 또는 '제17조 (비밀준수)')
        article_pattern = re.compile(r"(?:###?\s*)?(?:\[([^\]]+)\]\s*)?(제\s*\d+\s*조(?:\s*의\s*\d+)?)\s*([^\n]*)")
        matches = list(article_pattern.finditer(raw_text))

        if not matches:
            # 매칭되는 조항 번호 서식이 없는 경우 텍스트 전체를 하나의 근거 법률로 반환
            art_match = re.search(r"(제\s*\d+\s*조)", query_str)
            art_num = art_match.group(1) if art_match else "기본 조항"
            return [
                GroundingLaw(
                    법령명=fallback_law_name,
                    조번호=art_num,
                    본문=raw_text.strip(),
                    출처="국가법령정보센터"
                )
            ]

        grounding_laws = []
        for i, match in enumerate(matches):
            parsed_law_name = match.group(1) or fallback_law_name
            article_num = match.group(2).strip()
            title = match.group(3).strip().strip("()").strip()

            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)

            body = raw_text[start_pos:end_pos].strip()

            grounding_laws.append(
                GroundingLaw(
                    법령명=parsed_law_name,
                    조번호=article_num,
                    본문=f"({title})\n{body}" if title else body,
                    출처="국가법령정보센터"
                )
            )

        return grounding_laws

    def get_grounding(
        self, category: Category, contract_type: Optional[ContractType] = None
    ) -> List[GroundingLaw]:
        """주어진 조항 분류 카테고리(+계약유형)에 대한 국가 표준 근거 법조문을 수집합니다.

        contract_type이 SI/SM(하도급)이고 SUBCONTRACT_CATEGORY_QUERIES에 해당 카테고리
        오버라이드가 있으면 그걸 우선 쓰고, 없으면 CATEGORY_QUERIES(유형 무관 공용)로 폴백한다.
        """
        # 일반 조항(정의·효력·통지·해석 등)은 법령 grounding 대상이 아니다.
        if category == Category.GENERAL:
            return []
        # 무효 조합(예: WORKING_HOURS + SI_SUBCONTRACT) 조용히 넘어가지 않고 경고만 남긴다.
        # (AGENTS.md "조용한 실패 금지" — 그래도 조회 자체는 유형무관 공용값으로 계속 진행한다)
        if (
            contract_type is not None
            and category.contract_types
            and contract_type not in category.contract_types
        ):
            print(f"[Warning] 무효 조합: {category.value}는 {contract_type.value}에 유효한 카테고리가 아닙니다.")
        if contract_type in _SUBCONTRACT_TYPES and category in SUBCONTRACT_CATEGORY_QUERIES:
            query_str = SUBCONTRACT_CATEGORY_QUERIES[category]
        else:
            query_str = CATEGORY_QUERIES.get(category, "민법 도급")
        try:
            # MCP 클라이언트를 호출해 원본 법령 정보 획득
            raw_text = koreanLaw.query(query_str)
        except Exception as e:
            print(f"[Warning] 법률 수집 실패 (카테고리: {category}): {e}")
            return []

        return self._parse_raw_text_to_laws(query_str, raw_text)

    def query_law(self, clause_text: str) -> List[GroundingLaw]:
        """사용자 조항 본문 텍스트에 부합하는 연관 근거 법령 정보를 동적 질의하여 수집합니다."""
        # 명령어 버퍼 문제를 피하기 위해 동적 검색어는 60자로 슬라이싱 처리
        query_str = clause_text.strip()[:60]
        try:
            raw_text = koreanLaw.query(query_str)
        except Exception as e:
            print(f"[Warning] 법률 수집 실패 (질의: {query_str}): {e}")
            return []

        return self._parse_raw_text_to_laws(query_str, raw_text)
