from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data_plane.event_envelope import EventEnvelope
from data_plane.redis_stream_bus import RedisStreamBus

DATA_EVENTS_STREAM = "data.events"


@dataclass
class InMemoryDataEventRepository:
    items: List[Dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []

    async def save(self, event: Dict[str, Any]) -> Dict[str, Any]:
        self.items.append(event)
        return event

    async def list_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results = self.items
        if event_type:
            results = [x for x in results if x.get("event_type") == event_type]
        return list(results[-limit:])[::-1]


class DataBus:
    def __init__(
        self,
        repository: InMemoryDataEventRepository | Any | None = None,
        event_bus: RedisStreamBus | None = None,
        trace_store: Any | None = None,
        runtime_metrics: Any | None = None,
    ) -> None:
        self.repository = repository or InMemoryDataEventRepository()
        self.event_bus = event_bus
        self.trace_store = trace_store
        self.runtime_metrics = runtime_metrics

    async def _repo_save(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if hasattr(self.repository, "save"):
            return await self.repository.save(event)
        if hasattr(self.repository, "create"):
            return await self.repository.create(event)
        if hasattr(self.repository, "add"):
            return await self.repository.add(event)
        if hasattr(self.repository, "append"):
            return await self.repository.append(event)
        if hasattr(self.repository, "record"):
            return await self.repository.record(event)
        raise AttributeError(
            f"{self.repository.__class__.__name__} does not support save/create/add/append/record"
        )

    async def _repo_list_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if hasattr(self.repository, "list_events"):
            return await self.repository.list_events(event_type=event_type, limit=limit)
        if hasattr(self.repository, "list"):
            return await self.repository.list(event_type=event_type, limit=limit)
        if hasattr(self.repository, "get_events"):
            return await self.repository.get_events(event_type=event_type, limit=limit)
        if hasattr(self.repository, "query"):
            return await self.repository.query(event_type=event_type, limit=limit)
        return []

    async def _publish_to_event_bus(self, envelope: EventEnvelope) -> None:
        if self.event_bus is None:
            return
        await asyncio.to_thread(self.event_bus.publish, envelope)

    async def _observe_event(self, event: Dict[str, Any]) -> None:
        if self.trace_store is not None:
            await self.trace_store.append_event(event)
        if self.runtime_metrics is not None:
            await self.runtime_metrics.record_event(event)

    async def publish(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "data_plane",
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        final_payload: Dict[str, Any] = {}
        if payload:
            final_payload.update(payload)

        reserved_keys = {
            "source",
            "tenant_id",
            "correlation_id",
            "task_id",
            "workflow_id",
        }
        for key, value in kwargs.items():
            if key not in reserved_keys:
                final_payload[key] = value

        final_task_id = task_id or final_payload.get("task_id")
        final_workflow_id = workflow_id or final_payload.get("workflow_id")

        envelope = EventEnvelope.new(
            event_type=event_type,
            stream=DATA_EVENTS_STREAM,
            source=source,
            payload=final_payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            task_id=final_task_id,
            workflow_id=final_workflow_id,
            schema_version="1.0",
        )

        event = envelope.to_dict()
        saved = await self._repo_save(event)
        await self._observe_event(saved)
        await self._publish_to_event_bus(envelope)
        return saved

    async def router_success(
        self,
        *,
        task_id: str,
        route_to: str,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "task_id": task_id,
            "route_to": route_to,
        }
        if extra:
            payload["extra"] = extra
        return await self.publish(
            event_type="router.success",
            task_id=task_id,
            workflow_id=workflow_id,
            payload=payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )

    async def router_failed(
        self,
        *,
        task_id: str,
        error: str,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "task_id": task_id,
            "error": error,
        }
        if extra:
            payload["extra"] = extra
        return await self.publish(
            event_type="router.failed",
            task_id=task_id,
            workflow_id=workflow_id,
            payload=payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )

    async def task_executing(
        self,
        *,
        task_id: str,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        route_to: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {"task_id": task_id}
        if route_to is not None:
            payload["route_to"] = route_to
        if extra:
            payload["extra"] = extra
        return await self.publish(
            event_type="task.executing",
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload,
        )

    async def task_completed(
        self,
        *,
        task_id: str,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {"task_id": task_id}
        if result is not None:
            payload["result"] = result
        if extra:
            payload["extra"] = extra
        return await self.publish(
            event_type="task.completed",
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload,
        )

    async def task_failed(
        self,
        *,
        task_id: str,
        error: str,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "task_id": task_id,
            "error": error,
        }
        if extra:
            payload["extra"] = extra
        return await self.publish(
            event_type="task.failed",
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload,
        )

    async def workflow_started(
        self,
        *,
        workflow_id: str,
        task_id: str,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            event_type="workflow.started",
            workflow_id=workflow_id,
            task_id=task_id,
            payload={
                "workflow_id": workflow_id,
                "task_id": task_id,
            },
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )

    async def workflow_completed(
        self,
        *,
        workflow_id: str,
        task_id: str,
        result_summary: str,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            event_type="workflow.completed",
            workflow_id=workflow_id,
            task_id=task_id,
            payload={
                "workflow_id": workflow_id,
                "task_id": task_id,
                "result_summary": result_summary,
            },
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )

    async def list_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self._repo_list_events(
            event_type=event_type,
            limit=limit,
        )

    def ensure_consumer_group(self, group_name: str) -> None:
        if self.event_bus is not None:
            self.event_bus.ensure_group(DATA_EVENTS_STREAM, group_name)