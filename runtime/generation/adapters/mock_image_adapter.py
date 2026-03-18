from __future__ import annotations

from runtime.generation.base import BaseGenerationAdapter
from runtime.generation.exceptions import GenerationProviderError
from runtime.generation.types import (
    GenerationArtifact,
    GenerationCapability,
    GenerationHealthStatus,
    GenerationRequest,
    GenerationResponse,
    GenerationTaskType,
)


class MockImageAdapter(BaseGenerationAdapter):
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        if GenerationCapability.IMAGE not in self.config.capabilities:
            raise GenerationProviderError("mock image adapter is not configured for image capability")
        if request.task_type != GenerationTaskType.IMAGE:
            raise GenerationProviderError("mock image adapter only supports image generation")

        artifact = GenerationArtifact(
            uri="mock://image/generated-1.png",
            mime_type="image/png",
            metadata={
                "prompt": request.prompt,
                "width": request.width,
                "height": request.height,
            },
        )

        return GenerationResponse(
            provider=self.config.provider,
            model_name=self.config.model_name,
            task_type=GenerationTaskType.IMAGE,
            artifacts=[artifact],
            raw_response={"mock": True},
            latency_ms=1,
        )

    def health_check(self) -> GenerationHealthStatus:
        return GenerationHealthStatus(
            ok=True,
            provider=self.config.provider,
            model_name=self.config.model_name,
            detail="mock image adapter healthy",
        )