from __future__ import annotations

from typing import Any, Dict, Optional

from runtime.generation.types import (
    GenerationCapability,
    GenerationProvider,
    GenerationRequest,
    GenerationTaskType,
)
from runtime.generation_service import GenerationInvocationContext
from runtime.queue.task_models import GenerationTaskKind, GenerationTaskPayload, TaskEnvelope
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import InMemoryTaskStore
from runtime.workers.worker_base import WorkerBase


class GenerationWorker(WorkerBase):
    def __init__(
        self,
        *,
        queue_client: RedisStreamQueueClient,
        task_store: InMemoryTaskStore,
        generation_service: Any,
        consumer_name: str = "generation-worker-1",
    ) -> None:
        super().__init__(
            queue_client=queue_client,
            task_store=task_store,
            queue_name="generation",
            consumer_name=consumer_name,
        )
        self.generation_service = generation_service

    async def process_task(self, task: TaskEnvelope) -> Dict[str, Any]:
        payload = task.payload
        if not isinstance(payload, GenerationTaskPayload):
            raise TypeError("GenerationWorker received non-generation task payload")

        request = self._build_request(payload)
        context = self._build_context(task, payload)

        raw = await self.generation_service.generate(request=request, context=context)
        return self._normalize_result(raw)

    def _build_request(self, payload: GenerationTaskPayload) -> GenerationRequest:
        task_type = (
            GenerationTaskType.IMAGE
            if payload.kind == GenerationTaskKind.IMAGE
            else GenerationTaskType.VIDEO
        )

        extra_params = {}
        if payload.quality is not None:
            extra_params["quality"] = payload.quality
        if payload.style is not None:
            extra_params["style"] = payload.style
        if payload.resolution is not None:
            extra_params["resolution"] = payload.resolution

        return GenerationRequest(
            task_type=task_type,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            duration_seconds=payload.duration_seconds,
            fps=payload.fps,
            seed=payload.seed,
            count=payload.count,
            extra_params=extra_params,
            metadata=dict(payload.metadata),
        )

    def _build_context(
        self,
        task: TaskEnvelope,
        payload: GenerationTaskPayload,
    ) -> GenerationInvocationContext:
        requires = (
            frozenset({GenerationCapability.IMAGE})
            if payload.kind == GenerationTaskKind.IMAGE
            else frozenset({GenerationCapability.VIDEO})
        )

        return GenerationInvocationContext(
            tenant_id=payload.tenant_id or task.tenant_id or "dev",
            workflow_id=payload.workflow_id or task.workflow_id,
            correlation_id=payload.correlation_id or task.correlation_id,
            user_id=payload.user_id or task.user_id,
            model_ref=self._to_model_ref(payload.provider, payload.model),
            provider=self._to_provider(payload.provider),
            requires=requires,
            routing_policy=payload.routing_policy
            or ("image_first" if payload.kind == GenerationTaskKind.IMAGE else "video_first"),
            metadata={
                **dict(payload.metadata),
                "queue_name": task.queue_name,
                "worker_consumer": self.consumer_name,
            },
        )

    @staticmethod
    def _to_provider(value: Optional[str]) -> Optional[GenerationProvider]:
        if not value or not value.strip():
            return None
        try:
            return GenerationProvider(value.strip().lower())
        except ValueError:
            return None

    @staticmethod
    def _to_model_ref(provider: Optional[str], model: Optional[str]) -> Optional[str]:
        if provider and model:
            return f"{provider.strip().lower()}:{model.strip()}"
        return model

    @staticmethod
    def _normalize_result(raw: Any) -> Dict[str, Any]:
        if hasattr(raw, "provider") and hasattr(raw, "model_name") and hasattr(raw, "artifacts"):
            return {
                "provider": getattr(raw.provider, "value", raw.provider),
                "model": raw.model_name,
                "output": {
                    "task_type": getattr(getattr(raw, "task_type", None), "value", None),
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
                },
            }

        if isinstance(raw, dict):
            return raw

        return {"output": raw}