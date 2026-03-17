from __future__ import annotations

from runtime.models.base import BaseModelAdapter
from runtime.models.exceptions import (
    ModelCapabilityError,
    ModelRequestValidationError,
)
from runtime.models.types import ModelCapability, ModelRequest


class LLMAdapter(BaseModelAdapter):
    """
    Common contract for LLM-style chat/completion adapters.
    Concrete providers should inherit this class.
    """

    def validate_request(self, request: ModelRequest) -> None:
        if not request.messages:
            raise ModelRequestValidationError("request.messages must not be empty")

        if request.stream and ModelCapability.STREAMING not in self.config.capabilities:
            raise ModelCapabilityError(
                f"model '{self.config.model_name}' does not support streaming"
            )

        if request.tools and ModelCapability.TOOLS not in self.config.capabilities:
            raise ModelCapabilityError(
                f"model '{self.config.model_name}' does not support tool calling"
            )

        if request.response_format and ModelCapability.JSON_MODE not in self.config.capabilities:
            raise ModelCapabilityError(
                f"model '{self.config.model_name}' does not support structured/json responses"
            )