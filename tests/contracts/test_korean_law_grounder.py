"""KoreanLawGrounder.get_grounding 의 (category, contract_type) 쿼리 선택 규격 테스트.

docs/tasks/O_grounding_contract_type.md — SI/SM(하도급) 은 SW_FREELANCE 와 카테고리가
같아도 적용 법령이 다를 수 있어, SUBCONTRACT_CATEGORY_QUERIES 오버라이드를 우선 조회하고
없으면 CATEGORY_QUERIES(유형 무관 공용)로 폴백한다. 외부 koreanLaw MCP 호출은 mock 으로
대체해 실제 쿼리 문자열 선택 로직만 검증한다.
"""
from unittest.mock import MagicMock, patch

from contracts.enums import Category, ContractType
from contracts.implement.korean_law_grounder import KoreanLawGrounder


def _get_grounding(category, contract_type=None):
    grounder = KoreanLawGrounder()
    with patch("contracts.implement.korean_law_grounder.koreanLaw") as mock_law:
        mock_law.query.return_value = "본문"
        grounder.get_grounding(category, contract_type)
        return mock_law.query.call_args[0][0]


def test_SW는_공용_민법_쿼리():
    assert "민법" in _get_grounding(Category.PAYMENT, ContractType.SW_FREELANCE)


def test_SI_하도급은_오버라이드_쿼리():
    assert "하도급" in _get_grounding(Category.PAYMENT, ContractType.SI_SUBCONTRACT)


def test_SM_하도급도_동일_오버라이드():
    assert "하도급" in _get_grounding(Category.DELIVERY_INSPECTION, ContractType.SM_SUBCONTRACT)


def test_오버라이드_없는_카테고리는_SI여도_공용_폴백():
    assert "민법" in _get_grounding(Category.SCOPE_SOW, ContractType.SI_SUBCONTRACT)


def test_contract_type_생략시_기존과_동일하게_공용_쿼리():
    """하위호환: contract_type 없이 호출해도 기존 동작(공용 매핑) 그대로다."""
    assert "민법" in _get_grounding(Category.PAYMENT)


def test_GENERAL은_계약유형_무관_빈리스트():
    grounder = KoreanLawGrounder()
    with patch("contracts.implement.korean_law_grounder.koreanLaw") as mock_law:
        assert grounder.get_grounding(Category.GENERAL, ContractType.SI_SUBCONTRACT) == []
        mock_law.query.assert_not_called()


def test_정확_법령명_불일치는_본문_없이_NO_RESULT용_빈리스트():
    """부분 일치만 나온 경우 adapter의 빈 표식을 조문으로 가공하지 않는다."""
    grounder = KoreanLawGrounder()
    with patch("contracts.implement.korean_law_grounder.koreanLaw") as mock_law:
        mock_law.query.return_value = ""
        assert grounder.get_grounding(Category.PAYMENT) == []


# ── 신규 카테고리(INDUSTRIAL_SAFETY/INFO_SECURITY) 및 TERMINATION/LIABILITY 오버라이드 ──

def test_WARRANTY는_공용_민법_667조():
    assert "민법" in _get_grounding(Category.WARRANTY, ContractType.SW_FREELANCE)


def test_TERMINATION은_SI_하도급_오버라이드():
    """부당한 위탁취소 금지(하도급법 8조)는 민법 673조(도급인 임의해제권)와 별개 근거다."""
    assert "하도급" in _get_grounding(Category.TERMINATION, ContractType.SI_SUBCONTRACT)


def test_TERMINATION은_SW_FREELANCE에서_공용_민법_폴백():
    assert "민법" in _get_grounding(Category.TERMINATION, ContractType.SW_FREELANCE)


def test_LIABILITY는_SM_하도급_오버라이드():
    assert "하도급" in _get_grounding(Category.LIABILITY, ContractType.SM_SUBCONTRACT)


def test_INDUSTRIAL_SAFETY는_산업안전보건법():
    assert "산업안전보건법" in _get_grounding(Category.INDUSTRIAL_SAFETY, ContractType.SI_SUBCONTRACT)


def test_INFO_SECURITY는_정보통신망법():
    assert "정보통신망" in _get_grounding(Category.INFO_SECURITY, ContractType.SM_SUBCONTRACT)


def test_무효조합_경고_출력_후에도_조회는_계속됨(capsys):
    """WORKING_HOURS는 SI_SUBCONTRACT에 유효하지 않은 카테고리 — 경고만 찍고 폴백 조회는 계속한다."""
    result = _get_grounding(Category.WORKING_HOURS, ContractType.SI_SUBCONTRACT)
    assert "근로기준법" in result
    captured = capsys.readouterr()
    assert "무효 조합" in captured.out


def test_정적_카테고리_grounding은_프로세스_캐시를_재사용하고_반환값은_복사한다():
    """정적 질의는 재호출하지 않고, 호출자 변형이 캐시 원본에 영향을 주지 않는다."""
    client = MagicMock()
    client.query.return_value = "제665조(보수의 지급시기)\n도급인은 보수를 지급한다."
    grounder = KoreanLawGrounder(law_client=client)

    first = grounder.get_grounding(Category.PAYMENT, ContractType.SW_FREELANCE)
    first[0].본문 = "호출자가 바꾼 값"
    second = grounder.get_grounding(Category.PAYMENT, ContractType.SW_FREELANCE)

    assert client.query.call_count == 1
    assert second[0].본문 != "호출자가 바꾼 값"


def test_정확_법령명_불일치_NO_RESULT도_정적_캐시에_저장한다():
    """빈 목록은 정상 NO_RESULT이므로 반복 외부 호출을 만들지 않는다."""
    client = MagicMock()
    client.query.return_value = ""
    grounder = KoreanLawGrounder(law_client=client)

    assert grounder.get_grounding(Category.PAYMENT) == []
    assert grounder.get_grounding(Category.PAYMENT) == []
    assert client.query.call_count == 1


def test_조문번호_없는_사회보험_정적_grounding은_외부_호출하지_않는다():
    """단일 조문이 없는 사회보험 질의는 법령 전문을 가져오지 않는다."""
    client = MagicMock()
    grounder = KoreanLawGrounder(law_client=client)

    assert grounder.get_grounding(Category.SOCIAL_INSURANCE, ContractType.SW_EMPLOYMENT) == []
    client.query.assert_not_called()


def test_미매핑_카테고리는_민법_기본질의로_폴백하지_않는다():
    """매핑이 없는 기간 조항을 광범위한 민법 도급 질의로 바꾸지 않는다."""
    client = MagicMock()
    grounder = KoreanLawGrounder(law_client=client)

    assert grounder.get_grounding(Category.CONTRACT_PERIOD, ContractType.SW_FREELANCE) == []
    client.query.assert_not_called()


def test_조문_파서는_줄_시작_헤더만_읽고_본문_인용은_무시한다():
    """본문의 제656조 인용이 별도 GroundingLaw로 늘어나면 안 된다."""
    grounder = KoreanLawGrounder(law_client=MagicMock())
    raw_text = (
        "[민법] 제665조(보수의 지급시기)\n"
        "도급인은 보수를 지급한다. 이 경우 민법 제656조를 준용하지 않는다.\n"
    )

    laws = grounder._parse_raw_text_to_laws("민법 제665조 보수", raw_text)

    assert [(law.법령명, law.조번호) for law in laws] == [("민법", "제665조")]
    assert "제656조" in laws[0].본문


def test_조문_파서는_중복_헤더와_빈_본문을_제거한다():
    grounder = KoreanLawGrounder(law_client=MagicMock())
    raw_text = (
        "[하도급거래 공정화에 관한 법률] 제13조(하도급대금의 지급)\n"
        "원사업자는 대금을 지급한다.\n"
        "[하도급거래 공정화에 관한 법률] 제13조(하도급대금의 지급)\n"
        "중복 본문이다.\n"
        "[하도급거래 공정화에 관한 법률] 제14조(빈 조문)\n"
    )

    laws = grounder._parse_raw_text_to_laws(
        "하도급거래 공정화에 관한 법률 제13조 대금 지급", raw_text
    )

    assert len(laws) == 1
    assert laws[0].법령명 == "하도급거래 공정화에 관한 법률"
    assert laws[0].조번호 == "제13조"


def test_법률_명칭을_쿼리에서_정확히_보존한다():
    """'...에 관한 법률'도 기존의 단순 '법'처럼 잘리지 않아야 한다."""
    grounder = KoreanLawGrounder(law_client=MagicMock())

    laws = grounder._parse_raw_text_to_laws(
        "부정경쟁방지 및 영업비밀보호에 관한 법률 제2조 영업비밀",
        "제2조(정의)\n영업비밀의 정의\n",
    )

    assert laws[0].법령명 == "부정경쟁방지 및 영업비밀보호에 관한 법률"


def test_실제_복수_조문_헤더는_세건까지만_반환한다():
    grounder = KoreanLawGrounder(law_client=MagicMock())
    raw_text = "".join(
        f"제{article}조(제목)\n본문 {article}\n" for article in range(1, 6)
    )

    laws = grounder._parse_raw_text_to_laws("민법 제1조", raw_text)

    assert [law.조번호 for law in laws] == ["제1조", "제2조", "제3조"]


def test_동적_사용자_조항_query_law는_프로세스_캐시를_사용하지_않는다():
    """계약 원문에서 온 자유 질의는 서버 메모리에 장기 보관하지 않는다."""
    client = MagicMock()
    client.query.return_value = "제665조(보수의 지급시기)\n도급인은 보수를 지급한다."
    grounder = KoreanLawGrounder(law_client=client)

    grounder.query_law("사용자 계약서의 보수 지급 조항")
    grounder.query_law("사용자 계약서의 보수 지급 조항")

    assert client.query.call_count == 2


def test_외부_오류는_정적_캐시에_저장하지_않는다():
    """통신 오류는 다음 요청에서 정상적으로 재시도할 수 있어야 한다."""
    client = MagicMock()
    client.query.side_effect = RuntimeError("연결 실패")
    grounder = KoreanLawGrounder(law_client=client)

    for _ in range(2):
        try:
            grounder.get_grounding(Category.PAYMENT)
        except RuntimeError:
            pass

    assert client.query.call_count == 2
