"""카테고리 전용 법령 조회 도구의 공개 상태 계약 테스트."""

import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from contracts.enums import Category, ContractType
from contracts.models import GroundingLaw
from server.public_dto import GetCategoryGroundingResponse, PublicGroundingLaw
from server.server import get_category_grounding


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _law() -> GroundingLaw:
    return GroundingLaw(
        법령명="민법",
        조번호="제665조",
        본문="보수는 완성된 목적물의 인도와 동시에 지급하여야 한다.",
        출처="국가법령정보센터",
    )


def test_OK는_최소_한_건의_grounding이_필요하다():
    with pytest.raises(ValidationError, match="OK 상태에는"):
        GetCategoryGroundingResponse(
            status="OK",
            category="PAYMENT",
            grounding=[],
        )


def test_OK가_아닌_상태에는_grounding을_포함할_수_없다():
    with pytest.raises(ValidationError, match="OK가 아닌 상태에는"):
        GetCategoryGroundingResponse(
            status="NO_RESULT",
            category="PAYMENT",
            grounding=[
                PublicGroundingLaw(
                    법령명="민법",
                    조번호="제665조",
                    본문="본문",
                    출처="국가법령정보센터",
                )
            ],
        )


@pytest.mark.anyio
async def test_매핑된_카테고리_조회_성공은_OK와_법령을_반환한다():
    grounder = MagicMock()
    grounder.get_grounding.return_value = [_law()]

    with (
        patch("server.server.supports_static_grounding", return_value=True),
        patch("server.server.get_grounder", return_value=grounder),
    ):
        response = await get_category_grounding("PAYMENT", "SW_FREELANCE")

    assert response.status == "OK"
    assert response.category == "PAYMENT"
    assert response.contract_type == "SW_FREELANCE"
    assert len(response.grounding) == 1
    grounder.get_grounding.assert_called_once_with(
        Category.PAYMENT,
        ContractType.SW_FREELANCE,
    )


@pytest.mark.anyio
async def test_미매핑_카테고리는_외부_grounder를_생성하지_않는다():
    with (
        patch("server.server.supports_static_grounding", return_value=False),
        patch("server.server.get_grounder") as get_grounder,
    ):
        response = await get_category_grounding("CONTRACT_PERIOD", "SW_FREELANCE")

    assert response.status == "UNMAPPED_CATEGORY"
    assert response.grounding == []
    get_grounder.assert_not_called()


@pytest.mark.anyio
async def test_매핑은_있지만_검색_결과가_없으면_NO_RESULT다():
    grounder = MagicMock()
    grounder.get_grounding.return_value = []

    with (
        patch("server.server.supports_static_grounding", return_value=True),
        patch("server.server.get_grounder", return_value=grounder),
    ):
        response = await get_category_grounding("PAYMENT")

    assert response.status == "NO_RESULT"
    assert response.grounding == []


@pytest.mark.anyio
async def test_외부_법령_서비스_오류는_UPSTREAM_ERROR다():
    grounder = MagicMock()
    grounder.get_grounding.side_effect = RuntimeError("연결 실패")

    with (
        patch("server.server.supports_static_grounding", return_value=True),
        patch("server.server.get_grounder", return_value=grounder),
    ):
        response = await get_category_grounding("PAYMENT")

    assert response.status == "UPSTREAM_ERROR"
    assert response.grounding == []
    assert "연결 실패" not in (response.message or "")


@pytest.mark.anyio
async def test_외부_법령_서비스_시간초과는_TIMEOUT이다(monkeypatch):
    grounder = MagicMock()

    def delayed_result(category, contract_type):
        time.sleep(0.03)
        return [_law()]

    grounder.get_grounding.side_effect = delayed_result
    monkeypatch.setattr("server.server._CATEGORY_GROUNDING_TIMEOUT_SECONDS", 0.001)

    with (
        patch("server.server.supports_static_grounding", return_value=True),
        patch("server.server.get_grounder", return_value=grounder),
    ):
        response = await get_category_grounding("PAYMENT")

    assert response.status == "TIMEOUT"
    assert response.grounding == []
