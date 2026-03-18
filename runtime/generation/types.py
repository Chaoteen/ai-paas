from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional


class GenerationProvider(str, Enum):
    SEEDANCE = "seedance"
    MOCK_IMAGE = "mock_image"


class GenerationCapability(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class GenerationTaskType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True)
class GenerationConfig:
    provider: GenerationProvider
    model_name: str
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: float = 120.0
    max_retries: int = 1
    capabilities: frozenset[GenerationCapability] = field(default_factory=frozenset)
    default_headers: Mapping[str, str] = field(default_factory=dict)
    default_params: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def registry_key(self) -> str:
        return f"{self.provider.value}:{self.model_name}"


@dataclass(frozen=True)
class GenerationRequest:
    task_type: GenerationTaskType
    prompt: str
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    fps: Optional[int] = None
    seed: Optional[int] = None
    count: int = 1
    extra_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationArtifact:
    uri: str
    mime_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResponse:
    provider: GenerationProvider
    model_name: str
    task_type: GenerationTaskType
    artifacts: list[GenerationArtifact]
    raw_response: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None


@dataclass(frozen=True)
class GenerationHealthStatus:
    ok: bool
    provider: GenerationProvider
    model_name: str
    detail: str = ""


@dataclass(frozen=True)
class GenerationRegistryFilter:
    provider: Optional[GenerationProvider] = None
    requires: frozenset[GenerationCapability] = field(default_factory=frozenset)
    enabled_only: bool = True