from __future__ import annotations

import asyncio
import inspect
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from persistence.db import dispose_async_engine, get_async_session_factory
from runtime.queue.task_models import TaskEnvelope


class TaskStoreError(Exception):
    """Base exception for task store failures."""


class TaskStoreNotFoundError(TaskStoreError):
    """Raised when a task is not found."""


class TaskStoreConflictError(TaskStoreError):
    """Raised when a task already exists or a version/conflict is detected."""


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class TaskStore(ABC):
    @abstractmethod
    async def create(self, task: TaskEnvelope) -> TaskEnvelope:
        raise NotImplementedError

    @abstractmethod
    async def put(self, task: TaskEnvelope) -> TaskEnvelope:
        raise NotImplementedError

    @abstractmethod
    async def get(self, task_id: str) -> Optional[TaskEnvelope]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, task: TaskEnvelope) -> TaskEnvelope:
        raise NotImplementedError

    @abstractmethod
    async def exists(self, task_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, task_id: str) -> None:
        raise NotImplementedError


class InMemoryTaskStore(TaskStore):
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskEnvelope] = {}
        self._lock = asyncio.Lock()

    async def create(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)
        async with self._lock:
            if task.task_id in self._tasks:
                raise TaskStoreConflictError(f"Task already exists: task_id={task.task_id}")
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
                raise TaskStoreNotFoundError(f"Task not found for update: task_id={task.task_id}")
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
                raise TaskStoreNotFoundError(f"Task not found for delete: task_id={task_id}")
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


def get_task_store_backend_name() -> str:
    return os.getenv("TASK_STORE_BACKEND", "memory").strip().lower()


async def get_postgres_session_factory() -> Callable[[], AsyncSession]:
    """
    Formal single source of truth for Postgres async sessions.

    This intentionally delegates to persistence.db and does NOT cache a
    Database wrapper or any module-local engine/session factory state.
    """
    return get_async_session_factory()


async def _build_task_store() -> TaskStore:
    backend = get_task_store_backend_name()

    if backend == "memory":
        return InMemoryTaskStore()

    if backend == "postgres":
        from runtime.queue.postgres_task_store import PostgresTaskStore

        session_factory = await get_postgres_session_factory()
        return PostgresTaskStore(session_factory=session_factory)

    raise TaskStoreError(
        f"Unsupported TASK_STORE_BACKEND={backend!r}; expected 'memory' or 'postgres'"
    )


async def get_task_store() -> TaskStore:
    global _task_store
    if _task_store is not None:
        return _task_store

    async with _task_store_lock:
        if _task_store is None:
            _task_store = await _build_task_store()
        return _task_store


async def set_task_store(store: TaskStore) -> None:
    global _task_store
    if not isinstance(store, TaskStore):
        raise TaskStoreError(f"store must implement TaskStore, got {type(store)!r}")
    async with _task_store_lock:
        _task_store = store


async def reset_task_store() -> None:
    """
    Reset only the TaskStore singleton.

    This does not dispose the shared SQLAlchemy async engine. Use
    shutdown_task_store_runtime_state() when process/app shutdown should
    fully release DB resources.
    """
    global _task_store
    async with _task_store_lock:
        _task_store = None


async def shutdown_task_store_runtime_state() -> None:
    """
    Formal runtime shutdown hook.

    1. Reset task store singleton.
    2. Dispose the shared async engine/session factory owned by persistence.db.
    """
    await reset_task_store()
    await dispose_async_engine()