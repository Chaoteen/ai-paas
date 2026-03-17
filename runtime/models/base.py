from __future__ import annotations

from abc import ABC, abstractmethod

from runtime.models.types import HealthStatus, ModelConfig, ModelRequest, ModelResponse


class BaseModelAdapter(ABC):
    def __init__(self, config: ModelConfig) -> None:
        self._config = config

    @property
    def config(self) -> ModelConfig:
        return self._config

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> HealthStatus:
        raise NotImplementedError