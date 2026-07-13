"""1차 법률 grounding의 결정론적 체인 테스트."""

from unittest.mock import MagicMock

from adapter.korean_law_mcp import KoreanLawMCPClient


def test_query_refuses_partial_law_name_match():
    client = KoreanLawMCPClient()
    client.search_law = MagicMock(return_value='[{"lawName":"난민법", "mst":"123456"}]')
    client.get_law_text = MagicMock()

    assert client.query("민법 제665조 보수의 지급시기") == ""
    client.get_law_text.assert_not_called()


def test_query_chains_exact_law_match_to_article_text():
    client = KoreanLawMCPClient()
    client.search_law = MagicMock(return_value='[{"lawName":"민법", "mst":"012345"}]')
    client.get_law_text = MagicMock(return_value="제665조 본문")

    assert client.query("민법 제665조 보수의 지급시기") == "제665조 본문"
    client.get_law_text.assert_called_once_with(mst="012345", law_id=None, jo="066500")


def test_query_chains_actual_text_response_for_exact_law_name():
    client = KoreanLawMCPClient()
    client.search_law = MagicMock(return_value="""검색 결과 (총 1건):

1. 민법 [현행]
   - 법령ID: 001234
   - MST: 056789
""")
    client.get_law_text = MagicMock(return_value="제665조 본문")

    assert client.query("민법 제665조 보수의 지급시기") == "제665조 본문"
    client.get_law_text.assert_called_once_with(mst="056789", law_id="001234", jo="066500")
