# =================================================================
# WorkShield MCP 서버 이미지
# - Python(uv) + Node.js(kordoc, korean-law-mcp CLI) 런타임
# - data/03_normalized(정답) · data/migration(SQLite 스냅샷) · data/chroma(Chroma 스냅샷) 포함
# - 임베딩/리랭커 로컬 모델은 제외 (APP_ENV=prod → RunPod API 사용, adapter/__init__.py 참고)
# =================================================================
FROM python:3.13-slim

# Debian trixie의 Node.js는 korean-law-mcp(>=20.19)·kordoc(>=18) 요구사항을
# 충족한다. NodeSource 설치를 피해 빌드 신뢰성과 image layer 재현성을 높인다.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates nodejs npm \
    && npm install -g korean-law-mcp kordoc pdfjs-dist@4.10.38 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /usr/local/bin/

WORKDIR /app

# 의존성 레이어 캐싱: 소스 변경과 무관하게 의존성만 먼저 설치
# (sentence-transformers 등 dev 그룹은 제외 → 임베딩/리랭커 로컬 모델 미포함)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY data/03_normalized/ ./data/03_normalized/
COPY data/migration/ ./data/migration/
COPY data/chroma/ ./data/chroma/

RUN uv sync --frozen --no-dev

ENV APP_ENV=prod \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000

# FastMCP에는 별도 HTTP health endpoint가 없으므로, streamable HTTP listener가
# 포트를 열었는지 확인한다. 실제 MCP 연동 검증은 API readiness가 담당한다.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8000), timeout=5).close()"

# RUNPOD_SERVERLESS_API_KEY / RUNPOD_ENDPOINT_ID / LAW_OC 는 런타임에 --env-file 등으로 주입
CMD ["python", "src/app.py"]
