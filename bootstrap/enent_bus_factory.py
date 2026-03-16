from __future__ import annotations

import os

from data_plane.redis_stream_bus import RedisStreamBus
from control_plane.control_bus import ControlBus
from data_plane.data_bus import DataBus


def build_event_bus() -> RedisStreamBus:
    backend = os.getenv("AI_PAAS_EVENT_BUS", "redis").lower()

    if backend != "redis":
        raise ValueError(
            f"Unsupported AI_PAAS_EVENT_BUS={backend}. "
            "This module currently supports only 'redis'."
        )

    return RedisStreamBus.from_env()


def build_control_bus() -> ControlBus:
    event_bus = build_event_bus()
    return ControlBus(event_bus)


def build_data_bus() -> DataBus:
    event_bus = build_event_bus()
    return DataBus(event_bus)