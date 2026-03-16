from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data_plane.event_envelope import EventEnvelope
from data_plane.redis_stream_bus import RedisStreamBus


CONTROL_EVENTS_STREAM = "control.events"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InMemoryControlEventRepository:
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


class ControlBus:
    def __init__(
        self,
        repository: InMemoryControlEventRepository | Any | None = None,
        event_bus: RedisStreamBus | None = None,
    ) -> None:
        self.repository = repository or InMemoryControlEventRepository()
        self.event_bus = event_bus

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

    async def publish(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "control_plane",
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        final_payload: Dict[str, Any] = {}

        if payload:
            final_payload.update(payload)

        reserved_keys = {"source", "tenant_id", "correlation_id"}
        for key, value in kwargs.items():
            if key not in reserved_keys:
                final_payload[key] = value

        # 关键修复：把 agent_id 提升为顶层字段，供 Postgres repository 落列
        agent_id = None
        if "agent_id" in kwargs:
            agent_id = kwargs.get("agent_id")
        elif "agent_id" in final_payload:
            agent_id = final_payload.get("agent_id")

        event = {
            "event_id": None,
            "id": None,  # 某些 repository 直接用 id
            "event_type": event_type,
            "stream": CONTROL_EVENTS_STREAM,
            "source": source,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "payload": final_payload,
            "occurred_at": utc_now_iso(),
            "schema_version": "1.0",
        }

        if self.event_bus is not None:
            envelope = EventEnvelope.new(
                event_type=event_type,
                stream=CONTROL_EVENTS_STREAM,
                source=source,
                payload=final_payload,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
            )
            self.event_bus.publish(envelope)
            event["event_id"] = envelope.event_id
            event["id"] = envelope.event_id

        saved = await self._repo_save(event)
        return saved

    async def agent_registered(
        self,
        *,
        agent_id: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            event_type="agent.registered",
            tenant_id=tenant_id,
            agent_id=agent_id,
            payload={
                "agent_id": agent_id,
                "name": agent_name,
                "version": "1.0.0",
                "status": "active",
                "metadata": metadata or {},
            },
        )

    async def agent_heartbeat(
        self,
        *,
        agent_id: str,
        status: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            event_type="agent.heartbeat",
            tenant_id=tenant_id,
            agent_id=agent_id,
            payload={
                "agent_id": agent_id,
                "status": status,
            },
        )

    async def agent_removed(
        self,
        *,
        agent_id: str,
        tenant_id: Optional[str] = None,
        reason: str = "manual",
    ) -> Dict[str, Any]:
        return await self.publish(
            event_type="agent.removed",
            tenant_id=tenant_id,
            agent_id=agent_id,
            payload={
                "agent_id": agent_id,
                "reason": reason,
            },
        )

    async def agent_status_changed(
        self,
        *,
        agent_id: str,
        from_status: str,
        to_status: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            event_type="agent.status_changed",
            tenant_id=tenant_id,
            agent_id=agent_id,
            payload={
                "agent_id": agent_id,
                "from_status": from_status,
                "to_status": to_status,
            },
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
            self.event_bus.ensure_group(CONTROL_EVENTS_STREAM, group_name)