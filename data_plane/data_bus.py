from __future__ import annotations

from typing import List, Optional

from data_plane.data_events import DataEvent
from data_plane.repositories.data_event_repository import (
    DataEventRepository,
    InMemoryDataEventRepository,
)


class DataBus:
    """
    第五轮版本：
    DataBus 依赖 DataEventRepository。
    """

    def __init__(
        self,
        event_repository: Optional[DataEventRepository] = None,
    ):
        self.event_repository = event_repository or InMemoryDataEventRepository()

    def publish(self, event: DataEvent) -> DataEvent:
        return self.event_repository.save(event)

    def list_events(
        self,
        *,
        event_type: Optional[str] = None,
        task_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
    ) -> List[DataEvent]:
        return self.event_repository.list_events(
            event_type=event_type,
            task_id=task_id,
            envelope_id=envelope_id,
        )

    def count(self) -> int:
        return self.event_repository.count()

    def clear(self):
        self.event_repository.clear()