from __future__ import annotations

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
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_context(
        cls,
        context: ExecutionContext,
        *,
        model_ref: Optional[str] = None,
        provider: Optional[ModelProvider] = None,
        requires: Optional[frozenset[ModelCapability]] = None,
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

    def generate(
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
            )
        )
        adapter = self._registry.create_adapter(selection.registry_key)

        started = time.perf_counter()
        self._emit_trace_event(
            event_name="model.invoking",
            context=context,
            payload={
                "provider": selection.provider.value,
                "model_name": selection.model_name,
                "has_tools": bool(request.tools),
                "stream": request.stream,
            },
        )

        try:
            response = adapter.generate(request)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._emit_trace_event(
                event_name="model.failed",
                context=context,
                payload={
                    "provider": selection.provider.value,
                    "model_name": selection.model_name,
                    "latency_ms": elapsed_ms,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            self._emit_metric(
                name="runtime_model_failures_total",
                value=1,
                labels={
                    "provider": selection.provider.value,
                    "model_name": selection.model_name,
                    "error_type": exc.__class__.__name__,
                },
            )
            raise

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        self._emit_trace_event(
            event_name="model.completed",
            context=context,
            payload={
                "provider": response.provider.value,
                "model_name": response.model_name,
                "latency_ms": response.latency_ms or elapsed_ms,
                "finish_reason": response.finish_reason,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

        self._emit_metric(
            name="runtime_model_calls_total",
            value=1,
            labels={
                "provider": response.provider.value,
                "model_name": response.model_name,
            },
        )
        self._emit_metric(
            name="runtime_model_latency_ms",
            value=response.latency_ms or elapsed_ms,
            labels={
                "provider": response.provider.value,
                "model_name": response.model_name,
            },
        )
        self._emit_metric(
            name="runtime_model_tokens_total",
            value=response.usage.total_tokens,
            labels={
                "provider": response.provider.value,
                "model_name": response.model_name,
            },
        )

        return response

    def _emit_trace_event(
        self,
        *,
        event_name: str,
        context: ModelInvocationContext,
        payload: Dict[str, Any],
    ) -> None:
        if self._trace_store is None:
            return

        trace_methods = [
            "append_event",
            "record_event",
            "add_event",
            "write_event",
        ]
        trace_payload = {
            "workflow_id": context.workflow_id,
            "tenant_id": context.tenant_id,
            "correlation_id": context.correlation_id,
            "user_id": context.user_id,
            **context.metadata,
            **payload,
        }

        for method_name in trace_methods:
            method = getattr(self._trace_store, method_name, None)
            if callable(method):
                try:
                    method(
                        task_id=context.task_id,
                        event_name=event_name,
                        payload=trace_payload,
                    )
                except TypeError:
                    method(context.task_id, event_name, trace_payload)
                return

    def _emit_metric(self, *, name: str, value: int, labels: Dict[str, str]) -> None:
        if self._runtime_metrics is None:
            return

        metric_methods = [
            "observe",
            "record",
            "increment",
            "add_metric",
        ]
        for method_name in metric_methods:
            method = getattr(self._runtime_metrics, method_name, None)
            if callable(method):
                try:
                    method(name=name, value=value, labels=labels)
                except TypeError:
                    try:
                        method(name, value, labels)
                    except TypeError:
                        if method_name == "increment":
                            method(name)
                return