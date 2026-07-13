"""마이그레이션의 활성 표준 코퍼스 version 불변식을 검증한다."""
import importlib.util
from pathlib import Path

import pytest

from contracts.enums import Category, ContractType
from contracts.models import StandardClause


def _migrate_module():
    """숫자로 시작하는 `0.migrate.py`를 테스트에서 명시적으로 로드합니다."""
    path = Path(__file__).parents[2] / "src" / "pipe" / "0.migrate.py"
    spec = importlib.util.spec_from_file_location("pipe_migrate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _standard(contract_type: ContractType, version: str) -> StandardClause:
    return StandardClause(
        clause_id=f"{contract_type.value.lower()}-{version}-art1",
        contract_type=contract_type,
        category=Category.IP_OWNERSHIP,
        title="목적",
        text="계약의 목적을 정한다.",
        source="test",
        version=version,
    )


def test_유형별_단일_활성버전은_통과한다():
    validate_single_active_version = _migrate_module().validate_single_active_version

    validate_single_active_version([
        _standard(ContractType.SI_SUBCONTRACT, "2025"),
        _standard(ContractType.SI_SUBCONTRACT, "2025"),
        _standard(ContractType.SM_SUBCONTRACT, "2025"),
    ])


def test_유형별_복수_활성버전은_명시적으로_실패한다():
    validate_single_active_version = _migrate_module().validate_single_active_version

    with pytest.raises(ValueError, match="SI_SUBCONTRACT.*2022.*2025"):
        validate_single_active_version([
            _standard(ContractType.SI_SUBCONTRACT, "2022"),
            _standard(ContractType.SI_SUBCONTRACT, "2025"),
        ])
