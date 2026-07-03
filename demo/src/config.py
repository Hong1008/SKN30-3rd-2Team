
import os
from dotenv import load_dotenv
from pathlib import Path

# demo/.env 를 명시적으로 로드 (루트에서 streamlit 을 실행해도 데모 전용 키를 읽도록)
_DEMO_ENV = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_DEMO_ENV if _DEMO_ENV.exists() else None)

app_env = os.getenv("APP_ENV", "local")

WORKSHIELD_MCP_URL: str = os.getenv('WORKSHIELD_MCP_URL', 'http://localhost:8001/mcp')

# ──────────────────────────────────────────────────────────────
# LLM Provider 설정 (데모 요약·질의용)
# 세 공급자 모두 openai SDK 하나로 처리(신규 의존성 없음).
#   openai : OpenAI 정식 API — 요약 스트리밍(summarize_stream)만 Responses API + reasoning 사용
#            (Chat Completions는 reasoning 텍스트를 반환하지 않음), 그 외 경로는 Chat Completions 호환
#   gemini : Google Gemini 의 OpenAI 호환 Chat Completions 엔드포인트 (<think> 태그로 사고과정 표현)
#   custom : Runpod 등에 띄운 오픈모델(vLLM/TGI) OpenAI 호환 Chat Completions 엔드포인트 (동일)
# ──────────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")  # reasoning 계열 (gpt-4o-mini 등은 reasoning 미지원)
# reasoning 끄려면 OPENAI_REASONING_EFFORT="" 로 설정
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium") or None
OPENAI_REASONING_SUMMARY = os.getenv("OPENAI_REASONING_SUMMARY", "auto") or None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-31b-it")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

CUSTOM_LLM_BASE_URL = os.getenv("CUSTOM_LLM_BASE_URL")   # 예: https://<pod-id>-8000.proxy.runpod.net/v1 (미설정 시 custom 비활성)
CUSTOM_LLM_API_KEY = os.getenv("CUSTOM_LLM_API_KEY", "EMPTY")
CUSTOM_LLM_MODEL = os.getenv("CUSTOM_LLM_MODEL")         # 서빙 중인 HF 모델 id
# Qwen3 등 chat_template의 enable_thinking 스위치. 미설정(None) 시 모델 기본값 사용 — extra_body 자체를 보내지 않음.
_CUSTOM_LLM_ENABLE_THINKING = os.getenv("CUSTOM_LLM_ENABLE_THINKING")
CUSTOM_LLM_ENABLE_THINKING = (
    _CUSTOM_LLM_ENABLE_THINKING.lower() == "true" if _CUSTOM_LLM_ENABLE_THINKING is not None else None
)