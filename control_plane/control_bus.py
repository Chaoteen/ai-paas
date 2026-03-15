from __future__ import annotations

from typing import List, Optional

from control_plane.control_events import ControlEvent


class ControlBus:
    """
    内存版 Control Bus
    第三轮用于事件化 Agent 生命周期
    """

    def __init__(self):
        self._events: List[ControlEvent] = []

    def publish(self, event: ControlEvent) -> ControlEvent:
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