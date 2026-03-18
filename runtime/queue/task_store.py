from __future__ import annotations

from typing import Dict, Optional

from runtime.queue.task_models import TaskEnvelope


class InMemoryTaskStore:
    """
    Phase 16B:
    - simple in-memory task registry
    - later can be replaced by Redis/PostgreSQL-backed status store
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskEnvelope] = {}

    def put(self, task: TaskEnvelope) -> TaskEnvelope:
        self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> Optional[TaskEnvelope]:
        return self._tasks.get(task_id)

    def update(self, task: TaskEnvelope) -> TaskEnvelope:
        self._tasks[task.task_id] = task
        return task

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks


_task_store: Optional[InMemoryTaskStore] = None


def get_task_store() -> InMemoryTaskStore:
    global _task_store
    if _task_store is None:
        _task_store = InMemoryTaskStore()
    return _task_store