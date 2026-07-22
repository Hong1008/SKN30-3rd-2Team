import re
import threading
import time
from collections import OrderedDict
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
    # 사회보험은 단일 조문을 결정론적으로 특정할 수 없어 1차 grounding 대상에서 제외한다.
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


def get_static_grounding_query(
    category: Category,
    contract_type: Optional[ContractType] = None,
) -> Optional[str]:
    """외부 호출 없이 카테고리에 대응하는 특정 조문 질의를 반환한다.

    반환값이 ``None``이면 현재 정적 정책에 매핑되지 않은 카테고리다. 조회 결과가
    없다는 뜻은 아니며, 호출자는 이를 외부 검색의 빈 결과와 구분할 수 있다.
    """
    if category == Category.GENERAL:
        return None

    if contract_type in _SUBCONTRACT_TYPES and category in SUBCONTRACT_CATEGORY_QUERIES:
        query_str = SUBCONTRACT_CATEGORY_QUERIES[category]
    else:
        query_str = CATEGORY_QUERIES.get(category)

    if query_str is None or not re.search(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", query_str):
        return None
    return query_str


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

    def __init__(
        self,
        law_client=None,
        *,
        cache_ttl_seconds: float = 24 * 60 * 60,
        cache_max_entries: int = 64,
    ) -> None:
        """정적 카테고리 grounding 결과만 서버 프로세스 동안 캐시한다.

        사용자 조항 원문을 입력으로 하는 ``query_law``는 계약 정보를 오래 보관하지
        않도록 이 캐시에 넣지 않는다. 기본 클라이언트는 지연 참조하여 기존 테스트의
        module patch와 어댑터 싱글톤 조립을 모두 지원한다.
        """
        self._law_client = law_client
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache_max_entries = cache_max_entries
        self._cache: OrderedDict[
            tuple[Category, Optional[ContractType]], tuple[float, tuple[GroundingLaw, ...]]
        ] = OrderedDict()
        self._inflight: set[tuple[Category, Optional[ContractType]]] = set()
        self._cache_condition = threading.Condition(threading.RLock())

    @staticmethod
    def _copy_laws(laws: tuple[GroundingLaw, ...]) -> List[GroundingLaw]:
        """캐시 원본을 호출자가 변형하지 못하도록 깊은 복사본을 만든다."""
        return [law.model_copy(deep=True) for law in laws]

    def _cached_static_grounding(
        self,
        key: tuple[Category, Optional[ContractType]],
        loader,
    ) -> List[GroundingLaw]:
        """성공·NO_RESULT만 저장하는 TTL/LRU 및 key별 single-flight 캐시다."""
        with self._cache_condition:
            while True:
                cached = self._cache.get(key)
                if cached is not None:
                    expires_at, laws = cached
                    if expires_at > time.monotonic():
                        self._cache.move_to_end(key)
                        return self._copy_laws(laws)
                    del self._cache[key]
                if key not in self._inflight:
                    self._inflight.add(key)
                    break
                self._cache_condition.wait()

        try:
            laws = tuple(loader())
        except Exception:
            # 통신 실패는 다음 호출에서 재시도할 수 있도록 저장하지 않는다.
            with self._cache_condition:
                self._inflight.remove(key)
                self._cache_condition.notify_all()
            raise

        with self._cache_condition:
            self._cache[key] = (time.monotonic() + self._cache_ttl_seconds, laws)
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_max_entries:
                self._cache.popitem(last=False)
            self._inflight.remove(key)
            self._cache_condition.notify_all()
        return self._copy_laws(laws)

    def clear_cache(self) -> None:
        """프로세스 캐시를 비운다(테스트 격리와 운영상 명시적 갱신용)."""
        with self._cache_condition:
            self._cache.clear()

    def _parse_raw_text_to_laws(self, query_str: str, raw_text: str) -> List[GroundingLaw]:
        """조회된 줄글 형태의 법령 정보 텍스트를 구조화된 GroundingLaw 리스트로 가공합니다."""
        # 쿼리의 법령명은 ``법``뿐 아니라 ``...에 관한 법률`` 형식도 허용한다.
        law_name_match = re.search(
            r"([가-힣][가-힣ㆍ·\s]*?(?:법률|법))\s*제\s*\d+\s*조",
            query_str,
        )
        fallback_law_name = law_name_match.group(1).strip() if law_name_match else "관련 법령"

        # 조문 헤더는 반드시 줄 시작에 있어야 한다. 본문 속 "민법 제665조" 같은
        # 인용을 별도 조문으로 오인하면 법령 전문이 수백 건으로 증식한다.
        article_pattern = re.compile(
            r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\[([^\]\n]+)\][ \t]*)?"
            r"(제\s*\d+\s*조(?:\s*의\s*\d+)?)[ \t]*"
            r"(?:\(([^)\n]+)\))?[ \t]*$",
            re.MULTILINE,
        )
        matches = list(article_pattern.finditer(raw_text))

        if not matches:
            # 매칭되는 조항 번호 서식이 없는 경우 텍스트 전체를 하나의 근거 법률로 반환
            art_match = re.search(r"(제\s*\d+\s*조(?:\s*의\s*\d+)?)", query_str)
            art_num = art_match.group(1) if art_match else "기본 조항"
            body = raw_text.strip()
            if not body:
                return []
            return [
                GroundingLaw(
                    법령명=fallback_law_name,
                    조번호=art_num,
                    본문=body,
                    출처="국가법령정보센터",
                )
            ]

        grounding_laws = []
        seen: set[tuple[str, str]] = set()
        for i, match in enumerate(matches):
            parsed_law_name = match.group(1) or fallback_law_name
            article_num = match.group(2).strip()
            title = (match.group(3) or "").strip()

            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)

            body = raw_text[start_pos:end_pos].strip()
            if not body:
                continue

            key = (re.sub(r"\s+", " ", parsed_law_name).strip(), re.sub(r"\s+", "", article_num))
            if key in seen:
                continue
            seen.add(key)

            grounding_laws.append(
                GroundingLaw(
                    법령명=key[0],
                    조번호=article_num,
                    본문=f"({title})\n{body}" if title else body,
                    출처="국가법령정보센터",
                )
            )
            # 정적 질의는 조문 번호가 명확하므로 다수 헤더가 진짜여도 상한을 둔다.
            if len(grounding_laws) == 3:
                break

        return grounding_laws

    def get_grounding(
        self, category: Category, contract_type: Optional[ContractType] = None
    ) -> List[GroundingLaw]:
        """주어진 조항 분류 카테고리(+계약유형)에 대한 국가 표준 근거 법조문을 수집합니다.

        contract_type이 SI/SM(하도급)이고 SUBCONTRACT_CATEGORY_QUERIES에 해당 카테고리
        오버라이드가 있으면 그걸 우선 쓰고, 없으면 CATEGORY_QUERIES(유형 무관 공용)로 폴백한다.
        """
        # 무효 조합(예: WORKING_HOURS + SI_SUBCONTRACT) 조용히 넘어가지 않고 경고만 남긴다.
        # (AGENTS.md "조용한 실패 금지" — 그래도 조회 자체는 유형무관 공용값으로 계속 진행한다)
        if (
            contract_type is not None
            and category.contract_types
            and contract_type not in category.contract_types
        ):
            print(f"[Warning] 무효 조합: {category.value}는 {contract_type.value}에 유효한 카테고리가 아닙니다.")
        query_str = get_static_grounding_query(category, contract_type)
        if query_str is None:
            return []

        def load() -> List[GroundingLaw]:
            try:
                # MCP 클라이언트를 호출해 원본 법령 정보 획득
                client = self._law_client or koreanLaw
                raw_text = client.query(query_str)
            except Exception as e:
                raise RuntimeError(f"법률 수집 실패 (카테고리: {category.value}): {e}") from e

            # 정확 법령명 일치 실패는 adapter의 명시적 NO_RESULT 표식(빈 문자열)이다.
            if not raw_text.strip():
                return []
            return self._parse_raw_text_to_laws(query_str, raw_text)

        return self._cached_static_grounding((category, contract_type), load)

    def query_law(self, clause_text: str) -> List[GroundingLaw]:
        """사용자 조항 본문 텍스트에 부합하는 연관 근거 법령 정보를 동적 질의하여 수집합니다."""
        # 명령어 버퍼 문제를 피하기 위해 동적 검색어는 60자로 슬라이싱 처리
        query_str = clause_text.strip()[:60]
        try:
            client = self._law_client or koreanLaw
            raw_text = client.query(query_str)
        except Exception as e:
            raise RuntimeError(f"법률 수집 실패 (질의: {query_str}): {e}") from e

        if not raw_text.strip():
            return []

        return self._parse_raw_text_to_laws(query_str, raw_text)
