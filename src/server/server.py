import base64
import binascii
import logging
import uuid
from pathlib import Path
from typing import Optional

import anyio
from mcp.server.fastmcp import FastMCP, Context

from config import BASE_DIR
from contracts.enums import ContractType, Category, Deviation, ToxicPattern, ProgressPhase
from contracts.models import StandardClause, StandardSubChunk
from adapter import vector, db, reranker, embedder
from server.deps import get_parser, get_grounder
from core import classify_clause_deviation, select_best_match, assess_contract_scope as assess_scope_rules
from pipe.review_pipe import review_contract as review_contract_pipe
from pipe.exceptions import EmptyDocumentError, CorpusUnavailableError, InvalidConfigError, PipelineIntegrityError
from server.dto import (
    ParseContractResponse,
    GetGroundingResponse,
    MatchClauseResponse,
    MatchCandidate,
    ReviewContractResponse,
    ClassifyClauseResponse,
    ListContractTypesResponse,
    CategoryInfo,
    ListCategoriesResponse,
    ListToxicPatternsResponse,
    ToxicPatternDetail,
    ListToxicPatternDetailsResponse,
    AssessContractScopeResponse,
    ContractTypeScopeScore,
)

logger = logging.getLogger(__name__)

# 네트워크(streamable-http) 배포에서는 클라이언트와 서버가 파일시스템을 공유하지 않으므로,
# file_content(base64)로 받은 계약서를 이 디렉터리에 임시로 내려쓴 뒤 기존 file_path 경로로 처리한다.
# (data/README.md, .gitignore: 사용자 업로드 임시 파일 전용 디렉터리)
_UPLOAD_DIR = BASE_DIR / "data" / "99_uploads"

# kordoc 파서에 전달할 수 있는 계약서 원본 형식이다. 확장자 비교는 대소문자를 구분하지 않는다.
_SUPPORTED_CONTRACT_FILE_SUFFIXES = frozenset({
    ".hwp",
    ".hwpx",
    ".hwpml",
    ".pdf",
    ".xls",
    ".xlsx",
    ".docx",
})


def _validate_contract_file_suffix(file_name: str) -> None:
    """계약서 파일명이 kordoc 지원 확장자를 사용하는지 확인한다."""
    suffix = Path(file_name).suffix.lower()
    if suffix in _SUPPORTED_CONTRACT_FILE_SUFFIXES:
        return

    received = suffix or "확장자 없음"
    supported = ", ".join(item.removeprefix(".").upper() for item in sorted(_SUPPORTED_CONTRACT_FILE_SUFFIXES))
    raise ValueError(
        f"지원하지 않는 파일 형식: '{received}'. 지원 형식: {supported}."
    )


def _resolve_contract_file(
    file_path: Optional[str], file_content: Optional[str], file_name: Optional[str]
) -> tuple[str, Optional[Path]]:
    """file_path(로컬 경로) 또는 file_content(base64)+file_name 중 하나를 받아 실제 파일 경로를 반환한다.

    base64 입력인 경우 디코딩한 내용을 _UPLOAD_DIR에 임시 파일로 저장하고, 그 Path를 함께 반환하여
    호출부(도구 함수)가 사용 후 삭제하도록 한다. file_path 입력인 경우 두 번째 값은 None(정리 불필요).
    """
    if file_path and (file_content or file_name):
        raise ValueError("file_path와 file_content/file_name은 동시에 지정할 수 없습니다.")
    if file_path:
        _validate_contract_file_suffix(file_path)
        return file_path, None
    if not file_content or not file_name:
        raise ValueError(
            "file_path 또는 (file_content, file_name) 조합 중 하나를 입력해야 합니다. "
            "file_content는 base64 인코딩된 파일 바이트, file_name은 확장자 판별용 원본 파일명입니다."
        )

    _validate_contract_file_suffix(file_name)

    try:
        raw = base64.b64decode(file_content, validate=True)
    except binascii.Error as e:
        raise ValueError(f"file_content가 올바른 base64 형식이 아닙니다: {e}") from e

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = _UPLOAD_DIR / f"{uuid.uuid4().hex}{Path(file_name).suffix}"
    temp_path.write_bytes(raw)
    return str(temp_path), temp_path

def parse_contract(
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    file_name: Optional[str] = None,
    contract_type: Optional[str] = None,
) -> ParseContractResponse:
    """
    계약서 파일(HWP/HWPX/HWPML/PDF/XLS/XLSX/DOCX)을 조항 단위로 분해하여 반환합니다. 검토 파이프라인의 1단계이며,
    이 결과를 사람이 조항을 골라 match_clause/classify_clause 로 부분 검토하는 데도 쓸 수 있습니다.

    이탈 판정은 하지 않습니다 — 조항 분해만 수행합니다. 판정이 필요하면 review_contract 또는
    classify_clause 를 이어서 호출하세요.

    Args:
        file_path: 지원 형식의 분석할 계약서 절대 경로 (서버와 파일시스템을 공유할 때만 사용 가능. 로컬 stdio 배포용)
        file_content: base64 인코딩된 계약서 파일 바이트 (네트워크 배포용). file_name과 함께 지정해야 함.
        file_name: 원본 파일명 (HWP/HWPX/HWPML/PDF/XLS/XLSX/DOCX 확장자 판별용). file_content와 함께 지정해야 함.
        contract_type: 계약 종류 컨텍스트. 생략 가능. 가능한 값은 list_contract_types 로 조회하세요
            (하드코딩 금지 — 값 집합이 바뀔 수 있음).
    """
    ct: Optional[ContractType] = None
    if contract_type is not None:
        try:
            ct = ContractType(contract_type)
        except ValueError:
            raise ValueError(
                f"지원하지 않는 계약 종류: '{contract_type}'. "
                f"가능한 값: {[e.value for e in ContractType]}"
            )

    resolved_path, temp_path = _resolve_contract_file(file_path, file_content, file_name)
    try:
        # FileNotFoundError · RuntimeError(kordoc 변환 실패) → 그대로 raise → FastMCP error 응답
        clauses = get_parser().parse(resolved_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if not clauses:
        return ParseContractResponse(
            status="EMPTY_DOCUMENT",
            contract_type=ct.value if ct else None,
            clauses=[],
            message="조항을 찾을 수 없습니다. 스캔 PDF이거나 '제N조' 형식이 없는 문서일 가능성이 있습니다.",
        )

    return ParseContractResponse(
        status="OK",
        contract_type=ct.value if ct else None,
        clauses=clauses,
    )


def assess_contract_scope(
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    file_name: Optional[str] = None,
) -> AssessContractScopeResponse:
    """계약서가 지원 SW 표준계약서 범위에 속하는지 결정론적으로 판별합니다.

    파싱된 조항의 카테고리 앵커와 계약유형 표식을 비교할 뿐 파일명·LLM·법률상
    유효성 판단은 사용하지 않습니다. CONTRACT_TYPE_UNCERTAIN은 검토 차단이 아닌
    경고 상태입니다. 호출자는 사용자가 contract_type을 명시하면 그 값으로
    review_contract를 계속 호출할 수 있습니다.

    Args:
        file_path: 지원 형식의 분석할 계약서 절대 경로(로컬 stdio 환경용).
        file_content: base64 인코딩 계약서 바이트(네트워크 환경용).
        file_name: file_content와 함께 쓰는 HWP/HWPX/HWPML/PDF/XLS/XLSX/DOCX 원본 파일명.
    """
    resolved_path, temp_path = _resolve_contract_file(file_path, file_content, file_name)
    try:
        clauses = get_parser().parse(resolved_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if not clauses:
        return AssessContractScopeResponse(
            status="EMPTY_DOCUMENT",
            message="조항을 찾을 수 없습니다. 범위 판별을 위한 텍스트가 부족합니다.",
        )

    assessment = assess_scope_rules(clause.text for clause in clauses)
    candidates = [
        ContractTypeScopeScore(contract_type=contract_type.value, score=score)
        for contract_type, score in sorted(
            assessment.scores.items(), key=lambda item: (-item[1], item[0].value)
        )
    ]
    messages = {
        "IN_SCOPE": "지원 표준계약서와 비교할 후보입니다. suggested_contract_type으로 review_contract를 호출할 수 있습니다.",
        "CONTRACT_TYPE_UNCERTAIN": (
            "지원 SW 계약과 일부 공통점이 있으나 계약유형 근거가 충분하지 않습니다. "
            "경고를 확인한 뒤 사용자가 contract_type을 명시하여 review_contract를 호출할 수 있습니다."
        ),
        "OUT_OF_SCOPE": "현재 지원 SW 표준계약서 코퍼스와의 공통 근거가 부족한 문서입니다. 표준 대비 검토 대상에서 제외하는 것을 권장합니다.",
    }
    return AssessContractScopeResponse(
        status=assessment.status.value,
        suggested_contract_type=(
            assessment.suggested_contract_type.value
            if assessment.suggested_contract_type is not None else None
        ),
        candidates=candidates,
        matched_clause_count=assessment.matched_clause_count,
        exclusion_markers=list(assessment.exclusion_markers),
        message=messages[assessment.status.value],
    )


_MATCH_TOP_K_MAX = 10
_STANDARD_CLAUSES_TABLE = "standard_clauses"


def _load_standards(ct: ContractType) -> list[StandardClause]:
    rows = db.fetch_all(
        "SELECT * FROM standard_clauses WHERE contract_type = ?",
        ct.value,
    )
    return [StandardClause(**row) for row in rows]



_STANDARD_CLAUSES_COLLECTION = "standard_clauses"


def match_clause(
    clause_text: str,
    contract_type: str,
    top_k: int = 5,
) -> MatchClauseResponse:
    """
    단일 조항 텍스트와 가장 유사한 표준조항 후보를 유사도 순으로 검색합니다 (검색 전용, 이탈 판정 없음).

    이 도구는 "비슷한 표준조항이 뭐가 있나"만 답합니다. score는 검색 융합 점수(RRF/BM25 등)이며
    match_threshold 같은 판정 임계치와 스케일이 다르므로 "매칭 성공/실패"를 이 점수로 판단하지 마세요.
    "이 조항이 표준 대비 이탈(EXTRA/NONE)인가?"가 필요하면 classify_clause 를 쓰세요.
    이 도구가 반환하는 것은 "검토 후보" 목록일 뿐 최종 판정이 아닙니다.

    사용 예: 계약서 전체가 아니라 특정 조항 하나에 대해 어떤 표준조항이 대응되는지만 빠르게 훑어볼 때.

    Args:
        clause_text: 검색할 사용자 조항 본문 텍스트
        contract_type: 계약 종류. 가능한 값은 list_contract_types 로 조회하세요.
        top_k: 반환할 후보 수. 최대 10. 기본값 5.
    """
    try:
        ct = ContractType(contract_type)
    except ValueError:
        raise ValueError(
            f"지원하지 않는 계약 종류: '{contract_type}'. "
            f"가능한 값: {[e.value for e in ContractType]}"
        )

    top_k = min(top_k, _MATCH_TOP_K_MAX)

    query_vector = embedder.embed_query(clause_text)
    results = vector.hybrid_search(
        collection_name=_STANDARD_CLAUSES_COLLECTION,
        vector=query_vector,
        query=clause_text,
        metadata_filter={"contract_type": ct.value},
        top_k=top_k,
    )

    if not results:
        return MatchClauseResponse(
            status="NO_RESULT",
            contract_type=ct.value,
            candidates=[],
            message="일치하는 표준조항을 찾지 못했습니다.",
        )

    candidates = [
        MatchCandidate(
            clause_id=r["id"],
            score=r.get("fusion_score") or r.get("bm25_score") or r.get("dense_distance") or 0.0,
            standard_text=r["text"],
            title=r.get("title", ""),
            category=r.get("category", ""),
            source=r.get("source", ""),
        )
        for r in results
    ]

    return MatchClauseResponse(
        status="OK",
        contract_type=ct.value,
        candidates=candidates,
    )


def get_grounding(
    category: Optional[str] = None,
    clause_text: Optional[str] = None,
    contract_type: Optional[str] = None,
) -> GetGroundingResponse:
    """
    카테고리 또는 조항 본문에 해당하는 관련 법령 조문을 조회합니다.
    둘 다 제공되면 clause_text를 우선합니다 (korean-law-mcp는 단일 쿼리만 지원).

    반환되는 법령 조문은 참고용 근거 자료이며, "이 조항은 위법이다/유리하다" 같은 결론은
    포함하지 않습니다. 그런 해석이 필요한 문장은 이 도구의 출력을 그대로 사용자에게
    전달하지 말고, 반드시 "검토 후보/참고 자료"로 프레이밍하세요.

    Args:
        category: 조항 분류 카테고리. 가능한 값은 list_categories 로 조회하세요. 생략 가능.
        clause_text: 법령 조문을 조회할 조항 본문 텍스트. 생략 가능.
        contract_type: 계약 유형. SI/SM 하도급 계약은 같은 category라도 적용 법령이 다를 수
            있어(예: PAYMENT — SW는 민법, SI/SM은 하도급법), category와 함께 제공하면 더
            정확한 근거를 받습니다. clause_text 단독 조회에는 영향 없습니다. 생략 가능.
    """
    if category is None and clause_text is None:
        return GetGroundingResponse(
            status="INVALID_INPUT",
            grounding=[],
            message="category 또는 clause_text 중 하나 이상을 입력해야 합니다.",
        )

    if clause_text is not None:
        grounding = get_grounder().query_law(clause_text)
    else:
        try:
            cat = Category(category)
        except ValueError:
            raise ValueError(
                f"지원하지 않는 카테고리: '{category}'. "
                f"가능한 값: {[e.value for e in Category]}"
            )
        ct = None
        if contract_type is not None:
            try:
                ct = ContractType(contract_type)
            except ValueError:
                raise ValueError(
                    f"지원하지 않는 계약 종류: '{contract_type}'. "
                    f"가능한 값: {[e.value for e in ContractType]}"
                )
        grounding = get_grounder().get_grounding(cat, ct)

    if not grounding:
        return GetGroundingResponse(
            status="NO_RESULT",
            grounding=[],
            message="관련 법령 조문을 찾지 못했습니다.",
        )

    return GetGroundingResponse(status="OK", grounding=grounding)


# 상태별 한글 메시지 템플릿
PHASE_MESSAGES = {
    ProgressPhase.PREPARE: "검토 준비 중...",
    ProgressPhase.BATCH_SEARCH: "벡터 DB 배치 검색 중...",
    ProgressPhase.RERANK: "조항별 재정렬 중...",
    ProgressPhase.CLAUSE_REVIEW: "조항별 이탈 분류 중...",
    ProgressPhase.MISSING_DETECTION: "누락 표준조항 분석 중..."
}

async def review_contract(
    contract_type: str,
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    file_name: Optional[str] = None,
    ctx: Context = None,
) -> ReviewContractResponse:
    """
    계약서 파일 전체를 파싱하고 표준 대비 결과와 독소 신호를 함께 반환합니다.
    조항이 많은 계약서는 처리에 시간이 걸릴 수 있습니다(전체 조항을 배치로 검색·재정렬).

    contract_type은 비교할 표준 코퍼스를 선택하는 호출자 지정값입니다. 이 도구는 지원하는
    enum 값인지 확인할 뿐, 첨부 문서의 본문으로 계약 유형 일치 여부를 검증하거나 추천 유형으로
    자동 변경하지 않습니다. 유형이 불명확하거나 첨부 문서와 요청 유형이 다를 가능성이 있으면
    먼저 assess_contract_scope를 호출해 suggested_contract_type과 상태를 확인한 뒤, 사용자가
    최종 contract_type을 선택하세요. 자세한 클라이언트 처리 흐름은 src/server/README.md를
    참고하세요.

    각 사용자 조항은 두 독립 축으로 검토합니다.

    1. deviation: 표준조항 대비 대응·이탈·누락 신호(NO_MATCH/EXTRA/NONE/MISSING)
    2. toxic_patterns: 매칭 성패와 무관하게 독소 패턴 코퍼스를 역방향 검색한 신호

    두 축은 다음처럼 함께 해석합니다.

    | 표준 대비 결과 | 독소 신호 | 의미 |
    | --- | --- | --- |
    | EXTRA | 있음 | 표준 대응이 약하고 독소 패턴과도 유사 |
    | EXTRA | 없음 | 비표준 추가·변형이지만 알려진 독소 패턴 신호는 없음 |
    | NONE | 있음 | 표준 주제에는 대응하지만 내부 문구 일부가 독소 패턴과 유사 |
    | NONE | 없음 | 표준 주제 대응, 독소 신호도 없음 |

    빈 목록은 다음처럼 해석합니다.

    - toxic_patterns=[]: 임계값 이상의 알려진 패턴을 찾지 못했다는 뜻이며 안전·합법 판정이 아닙니다.
    - grounding=[]: 관련 법령이 없다는 뜻이 아닙니다. 1차는 주로 MISSING에만 정적 근거를 부착합니다.
    - results=[]: "문제 없음"이 아니라 status가 EMPTY_DOCUMENT, CORPUS_UNAVAILABLE,
      INVALID_CONFIG, PIPELINE_ERROR인지 먼저 확인해야 합니다.

    MISSING은 계약서 전체에서 표준조항이 누락된 후보이며 user_clause가 빈 문자열입니다.
    모든 결과는 검토 후보이며 위법·합법, 유불리, 승소 가능성을 단정하지 않습니다.

    특정 조항 한두 개만 빠르게 보고 싶다면 이 도구 대신 parse_contract 로 조항을 나눈 뒤
    classify_clause 를 개별 호출하면 빠릅니다. 단, classify_clause는 독소 패턴을 검색하지
    않으므로 독소 신호까지 필요하면 review_contract를 사용하세요.

    Args:
        contract_type: 비교 기준으로 쓸 계약 종류. 가능한 값은 list_contract_types 로 조회하세요.
            첨부 문서와의 일치는 자동 검증하지 않으므로, 유형이 불명확하면 먼저
            assess_contract_scope를 호출하세요.
        file_path: 지원 형식의 검토할 계약서 절대 경로 (서버와 파일시스템을 공유할 때만 사용 가능. 로컬 stdio 배포용)
        file_content: base64 인코딩된 계약서 파일 바이트 (네트워크 배포용). file_name과 함께 지정해야 함.
        file_name: 원본 파일명 (HWP/HWPX/HWPML/PDF/XLS/XLSX/DOCX 확장자 판별용). file_content와 함께 지정해야 함.
        ctx: MCP 실행 컨텍스트 (실시간 progress 보고용)
    """
    try:
        ct = ContractType(contract_type)
    except ValueError:
        raise ValueError(
            f"지원하지 않는 계약 종류: '{contract_type}'. "
            f"가능한 값: {[e.value for e in ContractType]}"
        )

    resolved_path, temp_path = _resolve_contract_file(file_path, file_content, file_name)
    try:
        # FileNotFoundError · RuntimeError(kordoc 실패) → 그대로 raise → FastMCP error 응답
        clauses = get_parser().parse(resolved_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    if not clauses:
        return ReviewContractResponse(
            status="EMPTY_DOCUMENT",
            contract_type=ct.value,
            results=[],
            message="조항을 찾을 수 없습니다. 스캔 PDF이거나 '제N조' 형식이 없는 문서일 가능성이 있습니다.",
        )

    standards = _load_standards(ct)
    if not standards:
        return ReviewContractResponse(
            status="CORPUS_UNAVAILABLE",
            contract_type=ct.value,
            results=[],
            message=f"{ct.value} 표준 코퍼스가 DB에 없습니다. `just build-db`를 먼저 실행하세요.",
        )

    # 1. 스레드 안전한 진행률 전달 콜백 정의
    def progress_callback(done: int, total: int, phase: ProgressPhase):
        if ctx:
            base_msg = PHASE_MESSAGES.get(phase, "검토 진행 중...")
            if phase == ProgressPhase.CLAUSE_REVIEW:
                msg = f"{base_msg} ({done}/{total})"
            else:
                msg = base_msg
            anyio.from_thread.run(ctx.report_progress, done, total, msg)

    try:
        results = await anyio.to_thread.run_sync(
            lambda: review_contract_pipe(
                clauses=clauses,
                contract_type=ct,
                retriever=vector,
                embedder=embedder,
                reranker=reranker,
                grounder=get_grounder(),
                all_standard_clauses=standards,
                progress_callback=progress_callback,
            )
        )
    except InvalidConfigError as e:
        return ReviewContractResponse(
            status="INVALID_CONFIG",
            contract_type=ct.value,
            results=[],
            message=str(e),
        )
    except PipelineIntegrityError as e:
        logger.error(f"[CRITICAL] 파이프라인 무결성 오류: {e}")
        return ReviewContractResponse(
            status="PIPELINE_ERROR",
            contract_type=ct.value,
            results=[],
            message="내부 오류가 발생했습니다. 관리자에게 문의하세요.",
        )
    except (CorpusUnavailableError, EmptyDocumentError) as e:
        # review_pipe 내부에서 raise된 경우 (이중 방어)
        logger.warning(f"review_pipe 내부 도메인 예외: {e}")
        return ReviewContractResponse(
            status="PIPELINE_ERROR",
            contract_type=ct.value,
            results=[],
            message=str(e),
        )
    except NotImplementedError:
        return ReviewContractResponse(
            status="PIPELINE_ERROR",
            contract_type=ct.value,
            results=[],
            message="review_contract 미구현 상태입니다. 담당자(팀원 C)에게 문의하세요.",
        )

    return ReviewContractResponse(
        status="OK",
        contract_type=ct.value,
        results=results,
    )


_CLASSIFY_TOP_K = 5


def classify_clause(
    clause_text: str,
    contract_type: str,
    match_threshold: float = 0.5,
) -> ClassifyClauseResponse:
    """
    단일 조항 텍스트 하나를 표준조항과 비교해 이탈 여부를 판정합니다 (부분 검토 워크플로우용).

    review_contract 전체를 돌리지 않고 "이 조항 하나만" 표준 대비 어떤지 알고 싶을 때 씁니다.
    match_clause 가 후보 나열까지만 하는 것과 달리, 이 도구는 재정렬(reranker) → 최적 매칭 선택
    → 이탈 분류까지 끝내 deviation(NO_MATCH/EXTRA/NONE) 하나를 확정해 반환합니다.

    MISSING은 이 도구로 나오지 않습니다. MISSING은 "표준조항이 계약서 전체에 없다"는 뜻이라
    조항 하나만으로는 판정할 수 없고, review_contract 로 전체를 봐야 발견됩니다.
    또한 이 도구는 독소 패턴 검색을 수행하지 않습니다. toxic_patterns가 필요하면
    review_contract를 사용하세요. 법령 조회도 수행하지 않아 grounding은 항상 빈 목록입니다.
    반환되는 deviation은 표준 대비 기계적 차이를 나타내는 "검토 후보" 표식이며, 위법 여부나
    유불리를 단정하지 않습니다. grounding=[]도 관련 법령이 없다는 뜻이 아닙니다.

    Args:
        clause_text: 판정할 사용자 조항 본문 텍스트
        contract_type: 계약 종류. 가능한 값은 list_contract_types 로 조회하세요.
        match_threshold: 대응 표준조항으로 인정할 최소 정규화 점수(0~1). 기본값 0.5.
    """
    try:
        ct = ContractType(contract_type)
    except ValueError:
        raise ValueError(
            f"지원하지 않는 계약 종류: '{contract_type}'. "
            f"가능한 값: {[e.value for e in ContractType]}"
        )

    standards = _load_standards(ct)
    if not standards:
        return ClassifyClauseResponse(
            status="CORPUS_UNAVAILABLE",
            contract_type=ct.value,
            message=f"{ct.value} 표준 코퍼스가 DB에 없습니다. `just build-db`를 먼저 실행하세요.",
        )
    standards_by_id = {std.clause_id: std for std in standards}

    query_vector = embedder.embed_query(clause_text)
    raw_hits = vector.hybrid_search(
        collection_name=_STANDARD_CLAUSES_COLLECTION,
        vector=query_vector,
        query=clause_text,
        metadata_filter={"contract_type": ct.value},
        top_k=_CLASSIFY_TOP_K,
    )
    if not raw_hits:
        return ClassifyClauseResponse(
            status="OK",
            contract_type=ct.value,
            deviation=Deviation.NO_MATCH.value,
            confidence=0.0,
        )

    reranked = reranker.rerank(clause_text, raw_hits, text_key="text", top_k=_CLASSIFY_TOP_K)
    candidates = []
    for hit in reranked:
        clause_id = hit.get("id") or hit.get("clause_id")
        standard = standards_by_id.get(clause_id) if clause_id else None
        if standard is not None:
            score = float(hit["rerank_score"]) if "rerank_score" in hit else 0.0
            candidates.append((standard, score))

    matched, score = select_best_match(candidates)
    deviation = classify_clause_deviation(matched, score, match_threshold)

    return ClassifyClauseResponse(
        status="OK",
        contract_type=ct.value,
        deviation=deviation.value,
        confidence=score,
        matched_standard=matched,
        grounding=[],  # 1차 검토 NONE/EXTRA에는 법령 근거 부착 안 함
    )


def list_contract_types() -> ListContractTypesResponse:
    """
    지원하는 계약 종류(contract_type) 전체 목록을 조회합니다.

    parse_contract / match_clause / review_contract / classify_clause 의 contract_type
    인자에 어떤 값을 넣을 수 있는지 하드코딩하지 말고 이 도구로 런타임에 확인하세요
    (지원 목록은 버전에 따라 추가/제거될 수 있습니다).
    """
    return ListContractTypesResponse(contract_types=[e.value for e in ContractType])


def list_categories(contract_type: Optional[str] = None) -> ListCategoriesResponse:
    """
    조항 분류 카테고리(category) 전체 목록을 설명·앵커 키워드와 함께 조회합니다.

    get_grounding 의 category 인자 값을 확인하거나, 계약서의 어떤 카테고리들이
    검토 대상인지 사람에게 설명할 때 사용하세요.

    Args:
        contract_type: 계약 유형. 제공하면 그 유형에 유효한 카테고리만 필터링합니다
            (예: SW_EMPLOYMENT는 WORKING_HOURS/HOLIDAY_LEAVE 포함, SW_FREELANCE는 제외).
            생략하면 전체 카테고리를 반환합니다.
    """
    ct = None
    if contract_type is not None:
        try:
            ct = ContractType(contract_type)
        except ValueError:
            raise ValueError(
                f"지원하지 않는 계약 종류: '{contract_type}'. "
                f"가능한 값: {[e.value for e in ContractType]}"
            )
    return ListCategoriesResponse(
        categories=[
            CategoryInfo(value=c.value, description=c.description, anchors=list(c.anchors))
            for c in Category
            if ct is None or not c.contract_types or ct in c.contract_types
        ]
    )


def list_toxic_patterns() -> ListToxicPatternsResponse:
    """
    탐지 대상 독소조항 패턴(toxic_pattern) 전체 목록을 조회합니다.

    review_contract 결과의 toxic_patterns 필드에 어떤 값이 나올 수 있는지 확인할 때 사용하세요.
    """
    return ListToxicPatternsResponse(patterns=[p.value for p in ToxicPattern])


def list_toxic_pattern_details() -> ListToxicPatternDetailsResponse:
    """탐지 대상 독소조항 패턴을 사람이 읽는 대표 제목과 함께 조회합니다 (패턴 enum 1건당 1행).

    review_contract 결과의 toxic_patterns 는 enum 값(예: IP_TOTAL_FREE)만 담고 있어,
    이를 사람이 읽는 제목으로 라벨링할 때 이 도구를 사용하세요. 반환값은 참고용 분류 정보이며
    특정 조항의 위법·불리함을 단정하지 않습니다.
    """
    rows = db.fetch_all(
        "SELECT pattern, MIN(category) AS category, MIN(title) AS title, "
        "COUNT(*) AS example_count "
        "FROM toxic_patterns GROUP BY pattern ORDER BY pattern"
    )
    return ListToxicPatternDetailsResponse(
        patterns=[ToxicPatternDetail(**row) for row in rows]
    )


def list_standard_clauses(contract_type: str) -> list[dict]:
    """계약 유형별 표준조항 목록을 (clause_id, title, category) 요약으로 읽기 전용 브라우징합니다.

    본문 전체가 필요하면 standard://{contract_type}/{clause_id} 를 읽으세요.
    """
    try:
        ct = ContractType(contract_type)
    except ValueError:
        raise ValueError(
            f"지원하지 않는 계약 종류: '{contract_type}'. "
            f"가능한 값: {[e.value for e in ContractType]}"
        )
    rows = db.fetch_all(
        "SELECT clause_id, title, category FROM standard_clauses WHERE contract_type = ?",
        ct.value,
    )
    return rows


def get_standard_clause(contract_type: str, clause_id: str) -> dict:
    """표준조항 원문 전체(제목·본문·출처·버전)를 clause_id로 조회합니다."""
    try:
        ContractType(contract_type)
    except ValueError:
        raise ValueError(
            f"지원하지 않는 계약 종류: '{contract_type}'. "
            f"가능한 값: {[e.value for e in ContractType]}"
        )
    row = db.fetch_one(
        "SELECT * FROM standard_clauses WHERE contract_type = ? AND clause_id = ?",
        (contract_type, clause_id),
    )
    if row is None:
        raise ValueError(f"표준조항을 찾을 수 없습니다: contract_type={contract_type}, clause_id={clause_id}")
    return row


class WorkShieldTools:
    """WorkShield의 도구·리소스를 주입받은 FastMCP 인스턴스에 등록한다.

    DB·벡터·모델은 공유 인프라 싱글턴으로 유지하되, 통신 서버 인스턴스는 이
    composition 단계에서만 받는다. 기존 모듈 함수는 하위호환·직접 단위 테스트를
    위해 보존하고, MCP에는 이 클래스의 인스턴스 메서드만 등록한다.
    """

    parse_contract = staticmethod(parse_contract)
    assess_contract_scope = staticmethod(assess_contract_scope)
    match_clause = staticmethod(match_clause)
    get_grounding = staticmethod(get_grounding)
    review_contract = staticmethod(review_contract)
    classify_clause = staticmethod(classify_clause)
    list_contract_types = staticmethod(list_contract_types)
    list_categories = staticmethod(list_categories)
    list_toxic_patterns = staticmethod(list_toxic_patterns)
    list_toxic_pattern_details = staticmethod(list_toxic_pattern_details)

    def __init__(self, mcp: FastMCP) -> None:
        for name in (
            "parse_contract",
            "assess_contract_scope",
            "match_clause",
            "get_grounding",
            "review_contract",
            "classify_clause",
            "list_contract_types",
            "list_categories",
            "list_toxic_patterns",
            "list_toxic_pattern_details",
        ):
            mcp.add_tool(getattr(self, name), name=name)

        # 리소스도 전역 데코레이터가 아니라, 주입된 앱에만 바인딩한다.
        @mcp.resource("standard://{contract_type}", mime_type="application/json")
        def standard_list_resource(contract_type: str) -> list[dict]:
            """계약 유형에 속한 표준조항의 식별자·제목·카테고리 목록을 반환한다.

            전체 본문과 출처가 필요하면 standard://{contract_type}/{clause_id} 리소스를 읽는다.
            contract_type에는 list_contract_types 도구가 반환한 값을 사용한다.
            """
            return list_standard_clauses(contract_type)

        @mcp.resource("standard://{contract_type}/{clause_id}", mime_type="application/json")
        def standard_detail_resource(contract_type: str, clause_id: str) -> dict:
            """계약 유형과 표준조항 식별자로 표준조항의 전체 내용을 반환한다.

            contract_type에는 list_contract_types 도구의 값을, clause_id에는 같은 유형의
            standard://{contract_type} 리소스가 반환한 식별자를 사용한다.
            """
            return get_standard_clause(contract_type, clause_id)
