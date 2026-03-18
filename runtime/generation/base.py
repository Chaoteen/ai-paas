from __future__ import annotations

from abc import ABC, abstractmethod

from runtime.generation.types import (
    GenerationConfig,
    GenerationHealthStatus,
    GenerationRequest,
    GenerationResponse,
)


class BaseGenerationAdapter(ABC):
    def __init__(self, config: GenerationConfig) -> None:
        self._config = config

    @property
    def config(self) -> GenerationConfig:
        return self._config

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> GenerationHealthStatus:
        raise NotImplementedError