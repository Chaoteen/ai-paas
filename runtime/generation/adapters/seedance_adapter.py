from __future__ import annotations

from typing import Any, Dict

import requests

from runtime.generation.base import BaseGenerationAdapter
from runtime.generation.exceptions import (
    GenerationAuthenticationError,
    GenerationConfigurationError,
    GenerationProviderError,
    GenerationTimeoutError,
)
from runtime.generation.types import (
    GenerationArtifact,
    GenerationCapability,
    GenerationHealthStatus,
    GenerationRequest,
    GenerationResponse,
    GenerationTaskType,
)


class SeedanceAdapter(BaseGenerationAdapter):
    """
    Seedance video generation adapter.

    This adapter is intentionally provider-agnostic in payload shape beyond the
    common fields we control. It is used as the platform's video generation
    provider contract.
    """

    def __init__(self, config) -> None:
        super().__init__(config)
        if not self.config.endpoint:
            raise GenerationConfigurationError("endpoint is required for seedance adapter")

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        if GenerationCapability.VIDEO not in self.config.capabilities:
            raise GenerationProviderError("seedance adapter is not configured for video capability")
        if request.task_type != GenerationTaskType.VIDEO:
            raise GenerationProviderError("seedance adapter only supports video generation requests")

        headers = {
            "Content-Type": "application/json",
            **dict(self.config.default_headers),
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "prompt": request.prompt,
            **dict(self.config.default_params),
        }
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        if request.width is not None:
            payload["width"] = request.width
        if request.height is not None:
            payload["height"] = request.height
        if request.duration_seconds is not None:
            payload["duration_seconds"] = request.duration_seconds
        if request.fps is not None:
            payload["fps"] = request.fps
        if request.seed is not None:
            payload["seed"] = request.seed
        payload.update(request.extra_params)

        try:
            response = requests.post(
                self.config.endpoint,
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise GenerationTimeoutError("seedance request timed out") from exc
        except requests.RequestException as exc:
            raise GenerationProviderError(f"seedance request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise GenerationAuthenticationError("seedance authentication failed")

        if response.status_code >= 400:
            raise GenerationProviderError(
                f"seedance returned status={response.status_code} body={response.text}"
            )

        body = response.json()
        artifacts = []

        for item in body.get("artifacts", []):
            artifacts.append(
                GenerationArtifact(
                    uri=item["uri"],
                    mime_type=item.get("mime_type", "video/mp4"),
                    metadata=item.get("metadata", {}),
                )
            )

        return GenerationResponse(
            provider=self.config.provider,
            model_name=body.get("model", self.config.model_name),
            task_type=GenerationTaskType.VIDEO,
            artifacts=artifacts,
            raw_response=body,
            latency_ms=None,
        )

    def health_check(self) -> GenerationHealthStatus:
        return GenerationHealthStatus(
            ok=True,
            provider=self.config.provider,
            model_name=self.config.model_name,
            detail="health check not actively probing upstream; adapter initialized",
        )