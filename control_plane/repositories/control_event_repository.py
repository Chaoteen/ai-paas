from __future__ import annotations

from typing import List, Optional

from control_plane.control_events import ControlEvent


class ControlEventRepository:
    """
    Control Event Repository 抽象基类。
    后续 PostgreSQL / Redis Stream / Kafka outbox 都可以实现这一层。
    """

    def save(self, event: ControlEvent) -> ControlEvent:
        raise NotImplementedError

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        aggregate_id: Optional[str] = None,
    ) -> List[ControlEvent]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError


class InMemoryControlEventRepository(ControlEventRepository):
    """
    第四轮先提供内存事件仓储实现。
    """

    def __init__(self):
        self._events: List[ControlEvent] = []

    def save(self, event: ControlEvent) -> ControlEvent:
        self._events.append(event)
        return event

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        aggregate_id: Optional[str] = None,
    ) -> List[ControlEvent]:
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if aggregate_id:
            events = [e for e in events if e.aggregate_id == aggregate_id]

        return list(events)

    def count(self) -> int:
        return len(self._events)

    def clear(self):
        self._events.clear()