from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class InMemoryRuntimeMetrics:
    counters: Dict[str, int] = field(default_factory=dict)

    def _inc(self, key: str, delta: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + delta

    async def record_event(self, event: Dict[str, Any]) -> None:
        event_type = str(event.get("event_type", "unknown"))
        self._inc("events_total")
        self._inc(f"event:{event_type}")

        if event_type == "task.submitted":
            self._inc("tasks_submitted")
        elif event_type == "task.completed":
            self._inc("tasks_completed")
        elif event_type == "task.failed":
            self._inc("tasks_failed")
        elif event_type == "tool.invoking":
            self._inc("tool_invocations")
        elif event_type == "llm.invoking":
            self._inc("llm_invocations")
        elif event_type == "security.denied":
            self._inc("security_denied")

    async def snapshot(self) -> Dict[str, int]:
        return dict(self.counters)