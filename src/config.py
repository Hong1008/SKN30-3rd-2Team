# =================================================================
# 프로젝트 전역 설정 관리 모듈
# 팀원 필독: .env 파일에 DB 연결 정보를 반드시 설정해야 합니다.
# =================================================================

import os
from dotenv import load_dotenv
from pathlib import Path


# 1. 프로젝트 루트 경로 설정 (프로젝트 어느 위치에서든 .env·data를 찾기 위함)
# config.py 는 src/ 안에 있으므로, 프로젝트 루트는 parent.parent 입니다.
# (이 값을 기준으로 data/, .env 등을 해석하므로 src/ 가 아닌 루트여야 합니다.)
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. 환경별 기본 설정 파일 (.env.local 또는 .env.prod) 및 비추적 시크릿(.env) 로드
app_env = os.getenv("APP_ENV", "local")
env_file = BASE_DIR / f".env.{app_env}"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)

env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv()

app_env = os.getenv("APP_ENV", "local")

LAW_OC: str | None = os.getenv('LAW_OC')
DB_BASE_FILE: str = os.getenv('DB_BASE_FILE', 'data/migration/contract.sqlite3')
# Chroma 는 SQLite(RDB)와 생명주기가 달라(재빌드 시 전체 삭제 후 재생성) 별도 폴더에 격리합니다.
CHROMA_DIR: str = os.getenv('CHROMA_DIR', 'data/chroma')

EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "dragonkue/BGE-m3-ko")
RERANKER_MODEL_NAME: str = os.getenv("RERANKER_MODEL_NAME", "dragonkue/bge-reranker-v2-m3-ko")

# 운영 RunPod Serverless 호출 전용 — Pod 생성·삭제 관리 키와 분리한다.
RUNPOD_SERVERLESS_API_KEY: str | None = os.getenv("RUNPOD_SERVERLESS_API_KEY")
RUNPOD_ENDPOINT_ID: str | None = os.getenv("RUNPOD_ENDPOINT_ID")
# Pod proxy를 사용할 때 Serverless endpoint 대신 이 URL의 /runsync로 요청한다.
RUNPOD_POD_BASE_URL: str | None = os.getenv("RUNPOD_POD_BASE_URL")
# 공개 RunPod Pod proxy의 Embedder·Reranker worker 인증 키다. RunPod 관리 키와
# 용도가 다르며 runtime에는 관리 키를 주입하지 않는다.
RUNPOD_EMBED_API_KEY: str | None = os.getenv("RUNPOD_EMBED_API_KEY")
