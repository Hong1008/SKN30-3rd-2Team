"""golden_b 범위 판별 매니페스트의 최소 계약 테스트."""

import json
from pathlib import Path


_MANIFEST = Path("quality/fixtures/track_b/golden_b/scope_manifest.json")


def test_범위_매니페스트의_원문과_기대값이_유효하다():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    documents = manifest["documents"]
    assert documents
    assert all((Path("quality/fixtures/track_b/golden_b") / document["path"]).is_file() for document in documents)
    assert {
        "raw/[별지 제6호의2서식] 표준근로계약서(농업ㆍ축산업ㆍ어업 분야).hwp",
        "raw/선원법.pdf",
    } <= {
        document["path"] for document in documents
        if document["expected_scope"] == "OUT_OF_SCOPE"
    }
