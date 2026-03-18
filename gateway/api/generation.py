from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bootstrap.generation_bootstrap import build_generation_service
from runtime.generation.types import (
    GenerationCapability,
    GenerationProvider,
    GenerationRequest,
    GenerationTaskType,
)
from runtime.generation_service import GenerationInvocationContext

router = APIRouter(tags=["generation"])


class ImageGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    size: Optional[str] = "1024x1024"
    quality: Optional[str] = None
    style: Optional[str] = None
    seed: Optional[int] = None
    num_images: int = 1
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    routing_policy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VideoGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    duration_seconds: int = 5
    resolution: Optional[str] = "720p"
    fps: Optional[int] = None
    seed: Optional[int] = None
    count: int = 1
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    routing_policy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationResponseModel(BaseModel):
    success: bool
    kind: str
    provider: Optional[str] = None
    model: Optional[str] = None
    output: Any = None
    error: Optional[Dict[str, Any]] = None


_generation_service = None


def get_generation_service():
    global _generation_service
    if _generation_service is None:
        _generation_service = build_generation_service()
    return _generation_service


def _parse_size(size: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if not size:
        return None, None
    try:
        width_str, height_str = size.lower().split("x", 1)
        return int(width_str.strip()), int(height_str.strip())
    except Exception:
        return None, None


def _parse_resolution(resolution: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if not resolution:
        return None, None

    value = resolution.strip().lower()
    preset_map = {
        "480p": (854, 480),
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "1440p": (2560, 1440),
        "4k": (3840, 2160),
    }
    if value in preset_map:
        return preset_map[value]

    return _parse_size(value)


def _to_provider(value: Optional[str]) -> Optional[GenerationProvider]:
    if not value or not value.strip():
        return None
    try:
        return GenerationProvider(value.strip().lower())
    except ValueError:
        return None


def _to_model_ref(provider: Optional[str], model: Optional[str]) -> Optional[str]:
    if provider and model:
        return f"{provider.strip().lower()}:{model.strip()}"
    return model


def _normalize_generation_response(kind: str, raw: Any) -> Dict[str, Any]:
    provider = None
    model_name = None
    output = None

    if raw is None:
        return {
            "success": False,
            "kind": kind,
            "provider": None,
            "model": None,
            "output": None,
            "error": {"message": "Generation service returned None"},
        }

    # dataclass GenerationResponse
    if hasattr(raw, "provider") and hasattr(raw, "model_name") and hasattr(raw, "artifacts"):
        provider = getattr(raw.provider, "value", raw.provider)
        model_name = raw.model_name
        output = {
            "task_type": getattr(getattr(raw, "task_type", None), "value", kind),
            "artifacts": [
                {
                    "uri": item.uri,
                    "mime_type": item.mime_type,
                    "metadata": dict(item.metadata),
                }
                for item in raw.artifacts
            ],
            "latency_ms": getattr(raw, "latency_ms", None),
            "raw_response": getattr(raw, "raw_response", None),
        }
        return {
            "success": True,
            "kind": kind,
            "provider": provider,
            "model": model_name,
            "output": output,
            "error": None,
        }

    if isinstance(raw, dict):
        return {
            "success": raw.get("success", True),
            "kind": kind,
            "provider": raw.get("provider"),
            "model": raw.get("model") or raw.get("model_name"),
            "output": raw.get("output", raw.get("result", raw)),
            "error": raw.get("error"),
        }

    return {
        "success": True,
        "kind": kind,
        "provider": None,
        "model": None,
        "output": raw,
        "error": None,
    }


@router.post("/generation/image", response_model=GenerationResponseModel)
async def generate_image(request: ImageGenerationRequest):
    try:
        service = get_generation_service()
        width, height = _parse_size(request.size)

        generation_request = GenerationRequest(
            task_type=GenerationTaskType.IMAGE,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=width,
            height=height,
            seed=request.seed,
            count=request.num_images,
            extra_params={
                "quality": request.quality,
                "style": request.style,
            },
            metadata=dict(request.metadata),
        )

        context = GenerationInvocationContext(
            tenant_id=request.tenant_id or "dev",
            workflow_id=request.workflow_id,
            correlation_id=request.correlation_id,
            user_id=request.user_id,
            model_ref=_to_model_ref(request.provider, request.model),
            provider=_to_provider(request.provider),
            requires=frozenset({GenerationCapability.IMAGE}),
            routing_policy=request.routing_policy or "image_first",
            metadata={"gateway_source": "gateway.api.generation", **dict(request.metadata)},
        )

        raw = await service.generate(request=generation_request, context=context)
        return GenerationResponseModel(**_normalize_generation_response("image", raw))

    except Exception as exc:
        message = str(exc)
        error_type = exc.__class__.__name__

        normalized_error = {
            "type": error_type,
            "message": message,
        }

        lowered = message.lower()
        requested_provider = request.provider or "auto"

        if error_type == "GenerationRegistryError" or "no generation model found" in lowered:
            normalized_error = {
                "type": "GenerationModelNotFound",
                "message": f"No generation model found for image request (provider={requested_provider})",
                "hint": "If you want mock image generation, start the gateway process with AI_PAAS_ENABLE_MOCK_IMAGE_PROVIDER=true",
            }

        return GenerationResponseModel(
            success=False,
            kind="image",
            provider=request.provider,
            model=request.model,
            output=None,
            error=normalized_error,
        )

@router.post("/generation/video", response_model=GenerationResponseModel)
async def generate_video(request: VideoGenerationRequest):
    try:
        service = get_generation_service()
        width, height = _parse_resolution(request.resolution)

        generation_request = GenerationRequest(
            task_type=GenerationTaskType.VIDEO,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=width,
            height=height,
            duration_seconds=request.duration_seconds,
            fps=request.fps,
            seed=request.seed,
            count=request.count,
            metadata=dict(request.metadata),
        )

        context = GenerationInvocationContext(
            tenant_id=request.tenant_id or "dev",
            workflow_id=request.workflow_id,
            correlation_id=request.correlation_id,
            user_id=request.user_id,
            model_ref=_to_model_ref(request.provider, request.model),
            provider=_to_provider(request.provider),
            requires=frozenset({GenerationCapability.VIDEO}),
            routing_policy=request.routing_policy or "video_first",
            metadata={"gateway_source": "gateway.api.generation", **dict(request.metadata)},
        )

        raw = await service.generate(request=generation_request, context=context)
        return GenerationResponseModel(**_normalize_generation_response("video", raw))

    except Exception as exc:
        message = str(exc)
        error_type = exc.__class__.__name__

        normalized_error = {
            "type": error_type,
            "message": message,
        }

        lowered = message.lower()
        requested_provider = request.provider or "auto"

        if error_type == "GenerationRegistryError" or "no generation model found" in lowered:
            normalized_error = {
                "type": "GenerationModelNotFound",
                "message": f"No generation model found for video request (provider={requested_provider})",
                "hint": "Seedance video generation requires provider registration, typically via AI_PAAS_SEEDANCE_ENDPOINT and AI_PAAS_SEEDANCE_API_KEY before gateway startup",
            }

        return GenerationResponseModel(
            success=False,
            kind="video",
            provider=request.provider,
            model=request.model,
            output=None,
            error=normalized_error,
        )