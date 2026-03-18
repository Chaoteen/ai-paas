from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from runtime.queue.task_models import TaskEnvelope


class TaskStoreError(Exception):
    """Base exception for task store failures."""


class TaskStoreNotFoundError(TaskStoreError):
    """Raised when a task is not found."""


class TaskStoreConflictError(TaskStoreError):
    """Raised when a task already exists or a version/conflict is detected."""


async def maybe_await(value: Any) -> Any:
    """
    Await a value only when it is awaitable.

    This is intentionally part of the task store contract surface because
    higher-level runtime components may depend on store implementations that
    are either native-async or sync-wrapped during migration periods.
    """
    if inspect.isawaitable(value):
        return await value
    return value


class TaskStore(ABC):
    """
    Durable task state abstraction.

    Contract goals:
    1. Stable async interface for gateway / dispatcher / workers.
    2. Swappable backend implementation (memory, postgres, redis, etc.).
    3. Explicit conflict and not-found semantics.
    """

    @abstractmethod
    async def create(self, task: TaskEnvelope) -> TaskEnvelope:
        """
        Create a new task record.

        Raises:
            TaskStoreConflictError: if the task already exists.
            TaskStoreError: on backend failure.
        """

    @abstractmethod
    async def put(self, task: TaskEnvelope) -> TaskEnvelope:
        """
        Upsert a task record.

        This method is kept as a first-class API because existing runtime
        paths already use put() semantically as 'save current state'.
        """

    @abstractmethod
    async def get(self, task_id: str) -> Optional[TaskEnvelope]:
        """
        Fetch a task by id.

        Returns:
            TaskEnvelope | None
        """

    @abstractmethod
    async def update(self, task: TaskEnvelope) -> TaskEnvelope:
        """
        Update an existing task record.

        Raises:
            TaskStoreNotFoundError: if task does not exist.
            TaskStoreError: on backend failure.
        """

    @abstractmethod
    async def exists(self, task_id: str) -> bool:
        """Return True when the task exists."""

    @abstractmethod
    async def delete(self, task_id: str) -> None:
        """
        Delete a task by id.

        Raises:
            TaskStoreNotFoundError: if task does not exist.
            TaskStoreError: on backend failure.
        """


class InMemoryTaskStore(TaskStore):
    """
    In-memory reference implementation.

    Notes:
    - This implementation is for tests and local development only.
    - It is still written with production-grade interface discipline:
      async API, lock protection, defensive validation, explicit errors.
    - It should be replaceable by PostgresTaskStore without changing callers.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskEnvelope] = {}
        self._lock = asyncio.Lock()

    async def create(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)
        async with self._lock:
            if task.task_id in self._tasks:
                raise TaskStoreConflictError(
                    f"Task already exists: task_id={task.task_id}"
                )
            self._tasks[task.task_id] = task
            return task

    async def put(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)
        async with self._lock:
            self._tasks[task.task_id] = task
            return task

    async def get(self, task_id: str) -> Optional[TaskEnvelope]:
        self._validate_task_id(task_id)
        async with self._lock:
            return self._tasks.get(task_id)

    async def update(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)
        async with self._lock:
            if task.task_id not in self._tasks:
                raise TaskStoreNotFoundError(
                    f"Task not found for update: task_id={task.task_id}"
                )
            self._tasks[task.task_id] = task
            return task

    async def exists(self, task_id: str) -> bool:
        self._validate_task_id(task_id)
        async with self._lock:
            return task_id in self._tasks

    async def delete(self, task_id: str) -> None:
        self._validate_task_id(task_id)
        async with self._lock:
            if task_id not in self._tasks:
                raise TaskStoreNotFoundError(
                    f"Task not found for delete: task_id={task_id}"
                )
            del self._tasks[task_id]

    @staticmethod
    def _validate_task(task: TaskEnvelope) -> None:
        if not isinstance(task, TaskEnvelope):
            raise TaskStoreError(
                f"Invalid task object type: expected TaskEnvelope, got {type(task)!r}"
            )
        if not getattr(task, "task_id", None):
            raise TaskStoreError("TaskEnvelope.task_id must not be empty")

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise TaskStoreError("task_id must be a non-empty string")


_task_store: Optional[TaskStore] = None
_task_store_lock = asyncio.Lock()


async def get_task_store() -> TaskStore:
    """
    Global task store accessor.

    For now, this returns the in-memory implementation.
    In Phase 16F/next, this factory should be extended to choose a backend
    from typed runtime settings and initialize a durable Postgres-backed store.
    """
    global _task_store
    if _task_store is not None:
        return _task_store

    async with _task_store_lock:
        if _task_store is None:
            _task_store = InMemoryTaskStore()
        return _task_store


async def set_task_store(store: TaskStore) -> None:
    """
    Override the global task store instance.

    Useful for tests and controlled bootstrap wiring.
    """
    global _task_store
    if not isinstance(store, TaskStore):
        raise TaskStoreError(
            f"store must implement TaskStore, got {type(store)!r}"
        )
    async with _task_store_lock:
        _task_store = store


async def reset_task_store() -> None:
    """
    Reset the global task store singleton.

    Intended for tests only.
    """
    global _task_store
    async with _task_store_lock:
        _task_store = None