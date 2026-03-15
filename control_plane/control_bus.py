from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class InMemoryControlEventRepository:
    """
    默认内存版控制事件仓库
    兼容旧测试，也可作为无数据库时的 fallback
    """

    def __init__(self):
        self._events: list[dict[str, Any]] = []

    async def append(self, event: dict[str, Any]) -> dict[str, Any]:
        self._events.append(event)
        return event

    async def list(
        self,
        event_type: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        events = self._events

        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]

        if agent_id:
            events = [e for e in events if e.get("agent_id") == agent_id]

        return list(reversed(events))[:limit]


class ControlBus:
    """
    控制面事件总线

    支持：
    - 默认内存仓库
    - 注入 PostgreSQL repository
    """

    def __init__(self, repository=None):
        self._repository = repository or InMemoryControlEventRepository()

    async def publish(
        self,
        event_type: str,
        agent_id: str | None = None,
        tenant_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": event_id or str(uuid4()),
            "event_type": event_type,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "payload": payload or {},
            "occurred_at": datetime.now(timezone.utc),
        }
        return await self._repository.append(event)

    async def publish_event(self, event: Any) -> dict[str, Any]:
        """
        兼容旧代码：允许直接传 dataclass / dict / object
        """
        normalized = self._normalize_event(event)
        if "id" not in normalized or not normalized["id"]:
            normalized["id"] = str(uuid4())
        if "occurred_at" not in normalized or not normalized["occurred_at"]:
            normalized["occurred_at"] = datetime.now(timezone.utc)
        if "payload" not in normalized or normalized["payload"] is None:
            normalized["payload"] = {}

        return await self._repository.append(normalized)

    async def list_events(
        self,
        event_type: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._repository.list(
            event_type=event_type,
            agent_id=agent_id,
            limit=limit,
        )

    async def count_events(
        self,
        event_type: str | None = None,
        agent_id: str | None = None,
    ) -> int:
        events = await self.list_events(event_type=event_type, agent_id=agent_id, limit=100000)
        return len(events)

    @staticmethod
    def _normalize_event(event: Any) -> dict[str, Any]:
        if isinstance(event, dict):
            return dict(event)

        if is_dataclass(event):
            return asdict(event)

        if hasattr(event, "__dict__"):
            return {
                k: v for k, v in vars(event).items()
                if not k.startswith("_")
            }

        raise TypeError(f"Unsupported event type: {type(event)}")