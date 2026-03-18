from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from runtime.execution_context import ExecutionContext
from runtime.generation.generation_registry import GenerationRegistry
from runtime.generation.selector import GenerationSelectionInput, GenerationSelector
from runtime.generation.types import (
    GenerationCapability,
    GenerationProvider,
    GenerationRequest,
    GenerationResponse,
)


@dataclass(frozen=True)
class GenerationInvocationContext:
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    model_ref: Optional[str] = None
    provider: Optional[GenerationProvider] = None
    requires: frozenset[GenerationCapability] = frozenset()
    routing_policy: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_context(
        cls,
        context: ExecutionContext,
        *,
        model_ref: Optional[str] = None,
        provider: Optional[GenerationProvider] = None,
        requires: Optional[frozenset[GenerationCapability]] = None,
        routing_policy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "GenerationInvocationContext":
        return cls(
            task_id=context.task_id,
            workflow_id=context.workflow_id,
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id,
            user_id=context.user_id,
            model_ref=model_ref,
            provider=provider,
            requires=requires or frozenset(),
            routing_policy=routing_policy,
            metadata=metadata or dict(context.metadata),
        )


class GenerationService:
    def __init__(
        self,
        registry: GenerationRegistry,
        trace_store: Optional[Any] = None,
        runtime_metrics: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._selector = GenerationSelector(registry)
        self._trace_store = trace_store
        self._runtime_metrics = runtime_metrics

    async def generate(
        self,
        *,
        request: GenerationRequest,
        context: GenerationInvocationContext,
    ) -> GenerationResponse:
        selection = self._selector.select(
            GenerationSelectionInput(
                model_ref=context.model_ref,
                provider=context.provider,
                requires=context.requires,
                routing_policy=context.routing_policy,
            )
        )
        adapter = self._registry.create_adapter(selection.registry_key)

        await self._emit_trace_event(
            event_type="generation.invoking",
            context=context,
            payload={
                "provider": selection.provider.value,
                "model_name": selection.model_name,
                "task_type": request.task_type.value,
                "routing_policy": context.routing_policy,
            },
        )

        response = adapter.generate(request)

        await self._emit_trace_event(
            event_type="generation.completed",
            context=context,
            payload={
                "provider": response.provider.value,
                "model_name": response.model_name,
                "task_type": response.task_type.value,
                "routing_policy": context.routing_policy,
                "artifact_count": len(response.artifacts),
            },
        )

        await self._emit_metric_event(
            event_type="generation.completed",
            context=context,
            payload={
                "provider": response.provider.value,
                "model_name": response.model_name,
                "task_type": response.task_type.value,
                "artifact_count": len(response.artifacts),
            },
        )

        return response

    async def _emit_trace_event(
        self,
        *,
        event_type: str,
        context: GenerationInvocationContext,
        payload: Dict[str, Any],
    ) -> None:
        if self._trace_store is None:
            return

        event = {
            "event_type": event_type,
            "task_id": context.task_id,
            "workflow_id": context.workflow_id,
            "tenant_id": context.tenant_id,
            "correlation_id": context.correlation_id,
            "source": "runtime.generation_service",
            "payload": {
                "user_id": context.user_id,
                **context.metadata,
                **payload,
            },
        }

        append_event = getattr(self._trace_store, "append_event", None)
        if callable(append_event):
            result = append_event(event)
            if inspect.isawaitable(result):
                await result
            return

    async def _emit_metric_event(
        self,
        *,
        event_type: str,
        context: GenerationInvocationContext,
        payload: Dict[str, Any],
    ) -> None:
        if self._runtime_metrics is None:
            return

        event = {
            "event_type": event_type,
            "task_id": context.task_id,
            "workflow_id": context.workflow_id,
            "tenant_id": context.tenant_id,
            "correlation_id": context.correlation_id,
            "source": "runtime.generation_service",
            "payload": {
                "user_id": context.user_id,
                **context.metadata,
                **payload,
            },
        }

        record_event = getattr(self._runtime_metrics, "record_event", None)
        if callable(record_event):
            result = record_event(event)
            if inspect.isawaitable(result):
                await result
            return