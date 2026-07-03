"""LLM provider 추상화의 공통 타입 (provider 간 결과 정규화)."""
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class ProviderConfig:
    name: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    supports_tools: bool = True
    reasoning_effort: Optional[str] = None  # openai reasoning 계열 모델 전용 (Responses API)
    reasoning_summary: Optional[str] = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON 문자열 (파싱 전)


@dataclass
class AssistantTurn:
    content: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


@runtime_checkable
class ChatModel(Protocol):
    """provider 교체 지점. 새 백엔드는 이 인터페이스만 구현하면 됨."""
    config: ProviderConfig

    def complete(self, messages: list[dict], tools: Optional[list[dict]] = None,
                 temperature: float = 0.2) -> AssistantTurn: ...

    def stream(self, messages: list[dict], temperature: float = 0.2): ...  # Iterator[tuple[str, str]] — (channel, delta), channel ∈ {"thought", "answer"}

    def parse(self, messages: list[dict], response_format: type[T],
              temperature: float = 0.2) -> Optional[T]: ...  # 구조화 출력; 파싱 실패/거부 시 None
