from data_plane.data_bus import DataBus
from data_plane.data_events import DataEvent
from data_plane.repositories.data_event_repository import InMemoryDataEventRepository


def test_publish_and_count_data_events():
    repo = InMemoryDataEventRepository()
    bus = DataBus(event_repository=repo)

    bus.publish(
        DataEvent.new(
            event_type="task.created",
            task_id="task_1",
            envelope_id="env_1",
        )
    )
    bus.publish(
        DataEvent.new(
            event_type="task.completed",
            task_id="task_1",
            envelope_id="env_1",
        )
    )

    assert bus.count() == 2


def test_filter_data_events():
    repo = InMemoryDataEventRepository()
    bus = DataBus(event_repository=repo)

    bus.publish(
        DataEvent.new(
            event_type="task.created",
            task_id="task_1",
            envelope_id="env_1",
        )
    )
    bus.publish(
        DataEvent.new(
            event_type="task.failed",
            task_id="task_2",
            envelope_id="env_2",
        )
    )

    assert len(bus.list_events(event_type="task.created")) == 1
    assert len(bus.list_events(task_id="task_2")) == 1
    assert len(bus.list_events(envelope_id="env_1")) == 1