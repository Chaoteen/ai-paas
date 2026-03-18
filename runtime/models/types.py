from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class ModelProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    MINIMAX = "minimax"
    DOUBAO = "doubao"


class ModelCapability(str, Enum):
    CHAT = "chat"
    TOOLS = "tools"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"
    VISION = "vision"
    EMBEDDINGS = "embeddings"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelConfig:
    provider: ModelProvider
    model_name: str
    display_name: Optional[str] = None
    version: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    organization: Optional[str] = None
    timeout_seconds: float = 60.0
    max_retries: int = 1
    capabilities: frozenset[ModelCapability] = field(default_factory=frozenset)
    default_headers: Mapping[str, str] = field(default_factory=dict)
    default_params: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def registry_key(self) -> str:
        if self.version:
            return f"{self.provider.value}:{self.model_name}:{self.version}"
        return f"{self.provider.value}:{self.model_name}"


@dataclass(frozen=True)
class ModelRequest:
    """
    ModelRequest only describes provider-facing inference parameters.

    Runtime context such as:
    - tenant_id
    - task_id
    - workflow_id
    - correlation_id
    - user_id

    must come from ExecutionContext, not from this object.
    """
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    tools: List[ToolSpec] = field(default_factory=list)
    tool_choice: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    provider: ModelProvider
    model_name: str
    message: ChatMessage
    finish_reason: Optional[str] = None
    usage: UsageInfo = field(default_factory=UsageInfo)
    raw_response: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    provider: ModelProvider
    model_name: str
    detail: str = ""


@dataclass(frozen=True)
class RegistryFilter:
    provider: Optional[ModelProvider] = None
    requires: frozenset[ModelCapability] = field(default_factory=frozenset)
    enabled_only: bool = True