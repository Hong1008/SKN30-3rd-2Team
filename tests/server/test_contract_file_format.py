"""계약서 업로드 파일 형식 검증 테스트."""

import base64
from pathlib import Path

import pytest

from server.server import _resolve_contract_file


@pytest.mark.parametrize(
    "file_name",
    ["contract.hwp", "contract.HWPX", "contract.hwpml", "contract.PDF", "contract.xls", "contract.XLSX", "contract.docx"],
)
def test_지원_파일_확장자는_base64_업로드를_허용한다(file_name: str):
    """지원 확장자는 대소문자와 관계없이 임시 파일로 해석한다."""
    encoded = base64.b64encode(b"test document").decode("ascii")

    resolved_path, temp_path = _resolve_contract_file(None, encoded, file_name)

    try:
        assert temp_path is not None
        assert Path(resolved_path).suffix.lower() == Path(file_name).suffix.lower()
        assert temp_path.read_bytes() == b"test document"
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@pytest.mark.parametrize("file_name", ["contract.txt", "contract.zip", "contract", "contract.hwp.exe"])
def test_미지원_파일_확장자는_임시_저장_전에_거절한다(file_name: str):
    """미지원 형식은 kordoc 호출 전에 지원 형식 안내와 함께 실패한다."""
    encoded = base64.b64encode(b"test document").decode("ascii")

    with pytest.raises(ValueError, match="지원하지 않는 파일 형식") as exc_info:
        _resolve_contract_file(None, encoded, file_name)

    assert "HWPX" in str(exc_info.value)


def test_로컬_경로도_미지원_파일_확장자를_거절한다():
    """로컬 stdio 입력도 업로드 입력과 같은 형식 제한을 적용한다."""
    with pytest.raises(ValueError, match="지원하지 않는 파일 형식"):
        _resolve_contract_file("/tmp/contract.txt", None, None)
