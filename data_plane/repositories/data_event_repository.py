from __future__ import annotations

from typing import List, Optional

from data_plane.data_events import DataEvent


class DataEventRepository:
    """
    Data Event Repository 抽象基类。
    后续可以替换成 PostgreSQL / Redis Stream / Kafka。
    """

    def save(self, event: DataEvent) -> DataEvent:
        raise NotImplementedError

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        task_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
    ) -> List[DataEvent]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError


class InMemoryDataEventRepository(DataEventRepository):
    """
    第五轮先提供内存实现。
    """

    def __init__(self):
        self._events: List[DataEvent] = []

    def save(self, event: DataEvent) -> DataEvent:
        self._events.append(event)
        return event

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        task_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
    ) -> List[DataEvent]:
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if task_id:
            events = [e for e in events if e.task_id == task_id]

        if envelope_id:
            events = [e for e in events if e.envelope_id == envelope_id]

        return list(events)

    def count(self) -> int:
        return len(self._events)

    def clear(self):
        self._events.clear()