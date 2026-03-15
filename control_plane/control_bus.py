from __future__ import annotations

from typing import List, Optional

from control_plane.control_events import ControlEvent
from control_plane.repositories.control_event_repository import (
    ControlEventRepository,
    InMemoryControlEventRepository,
)


class ControlBus:
    """
    第四轮版本：
    ControlBus 不再直接持有内存 list，
    而是依赖 ControlEventRepository。
    """

    def __init__(
        self,
        event_repository: Optional[ControlEventRepository] = None,
    ):
        self.event_repository = event_repository or InMemoryControlEventRepository()

    def publish(self, event: ControlEvent) -> ControlEvent:
        return self.event_repository.save(event)

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        aggregate_id: Optional[str] = None,
    ) -> List[ControlEvent]:
        return self.event_repository.list_events(
            event_type=event_type,
            aggregate_id=aggregate_id,
        )

    def count(self) -> int:
        return self.event_repository.count()

    def clear(self):
        self.event_repository.clear()