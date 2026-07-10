"""지원 계약 범위 판별 규칙의 결정론적 규격 테스트."""

from contracts.enums import ContractType
from core.contract_scope import ScopeStatus, assess_contract_scope


def test_농축어업_근로계약서는_명시적_범위_밖이다():
    assessment = assess_contract_scope([
        "근로자는 농업 및 축산업 업무에 종사하며, 어업 작업 장소는 사용자가 정한다.",
        "임금과 근로시간은 근로기준법에 따른다.",
    ])

    assert assessment.status == ScopeStatus.OUT_OF_SCOPE
    assert "농업" in assessment.exclusion_markers


def test_선원법_문서는_명시적_범위_밖이다():
    assessment = assess_contract_scope([
        "선박소유자는 선원의 승무와 선박 운항에 관한 사항을 정한다.",
        "선원의 근로시간 및 휴식시간에 관한 사항을 적용한다.",
    ])

    assert assessment.status == ScopeStatus.OUT_OF_SCOPE
    assert "선원" in assessment.exclusion_markers


def test_유형_근거가_충분한_sw_프리랜서_계약서는_범위_안이다():
    assessment = assess_contract_scope([
        "프리랜서는 소프트웨어 개발 용역의 업무 범위를 수행한다.",
        "용역 대금 지급 시기와 결과물의 저작권 귀속을 정한다.",
        "계약 해지와 비밀 유지 의무를 정한다.",
    ])

    assert assessment.status == ScopeStatus.IN_SCOPE
    assert assessment.suggested_contract_type == ContractType.SW_FREELANCE
    assert assessment.matched_clause_count >= 2


def test_sw_도메인이나_유형을_특정하기_어려우면_경고_상태다():
    assessment = assess_contract_scope([
        "소프트웨어 관련 업무의 계약 기간과 보수 지급 방법을 정한다.",
        "업무 범위와 비밀 유지 의무를 정한다.",
    ])

    assert assessment.status == ScopeStatus.CONTRACT_TYPE_UNCERTAIN
    assert assessment.suggested_contract_type is not None
