from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from runtime.execution_context import ExecutionContext
from runtime.models.model_registry import ModelRegistry
from runtime.models.selector import ModelSelectionInput, ModelSelector
from runtime.models.types import ModelCapability, ModelProvider, ModelRequest, ModelResponse


@dataclass(frozen=True)
class ModelInvocationContext:
    """
    Runtime-aligned invocation context.

    All runtime-scoped identity fields align to ExecutionContext naming.
    """
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    model_ref: Optional[str] = None
    provider: Optional[ModelProvider] = None
    requires: frozenset[ModelCapability] = frozenset()
    routing_policy: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_context(
        cls,
        context: ExecutionContext,
        *,
        model_ref: Optional[str] = None,
        provider: Optional[ModelProvider] = None,
        requires: Optional[frozenset[ModelCapability]] = None,
        routing_policy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ModelInvocationContext":
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


class ModelService:
    """
    Runtime-facing model invocation service.

    Responsibilities:
    - choose a model via ModelSelector
    - instantiate adapter via ModelRegistry
    - invoke provider
    - emit internal trace/metrics
    """

    def __init__(
        self,
        registry: ModelRegistry,
        trace_store: Optional[Any] = None,
        runtime_metrics: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._selector = ModelSelector(registry)
        self._trace_store = trace_store
        self._runtime_metrics = runtime_metrics

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    async def generate(
        self,
        *,
        request: ModelRequest,
        context: ModelInvocationContext,
    ) -> ModelResponse:
        selection = self._selector.select(
            ModelSelectionInput(
                model_ref=context.model_ref,
                provider=context.provider,
                requires=context.requires,
                routing_policy=context.routing_policy,
            )
        )
        adapter = self._registry.create_adapter(selection.registry_key)

        started = time.perf_counter()
        await self._emit_trace_event(
            event_type="model.invoking",
            context=context,
            payload={
                "provider": selection.provider.value,
                "model_name": selection.model_name,
                "routing_policy": context.routing_policy,
                "has_tools": bool(request.tools),
                "stream": request.stream,
            },
        )

        try:
            response = adapter.generate(request)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            await self._emit_trace_event(
                event_type="model.failed",
                context=context,
                payload={
                    "provider": selection.provider.value,
                    "model_name": selection.model_name,
                    "routing_policy": context.routing_policy,
                    "latency_ms": elapsed_ms,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            await self._emit_metric_event(
                event_type="model.failed",
                context=context,
                payload={
                    "provider": selection.provider.value,
                    "model_name": selection.model_name,
                    "routing_policy": context.routing_policy,
                    "error_type": exc.__class__.__name__,
                },
            )
            raise

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        await self._emit_trace_event(
            event_type="model.completed",
            context=context,
            payload={
                "provider": response.provider.value,
                "model_name": response.model_name,
                "routing_policy": context.routing_policy,
                "latency_ms": response.latency_ms or elapsed_ms,
                "finish_reason": response.finish_reason,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

        await self._emit_metric_event(
            event_type="model.completed",
            context=context,
            payload={
                "provider": response.provider.value,
                "model_name": response.model_name,
                "routing_policy": context.routing_policy,
                "latency_ms": response.latency_ms or elapsed_ms,
                "total_tokens": response.usage.total_tokens,
            },
        )

        return response

    async def _emit_trace_event(
        self,
        *,
        event_type: str,
        context: ModelInvocationContext,
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
            "source": "runtime.model_service",
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

        for method_name in ("record_event", "add_event", "write_event"):
            method = getattr(self._trace_store, method_name, None)
            if callable(method):
                result = method(event)
                if inspect.isawaitable(result):
                    await result
                return

    async def _emit_metric_event(
        self,
        *,
        event_type: str,
        context: ModelInvocationContext,
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
            "source": "runtime.model_service",
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

        for method_name in ("observe", "record", "increment", "add_metric"):
            method = getattr(self._runtime_metrics, method_name, None)
            if callable(method):
                try:
                    result = method(event_type, payload)
                except TypeError:
                    try:
                        result = method(name=event_type, value=1, labels=payload)
                    except TypeError:
                        result = method(event)
                if inspect.isawaitable(result):
                    await result
                return