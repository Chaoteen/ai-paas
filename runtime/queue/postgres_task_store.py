from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.task_repository import (
    TaskRepository,
    TaskRepositoryConflictError,
    TaskRepositoryNotFoundError,
)
from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import (
    TaskStore,
    TaskStoreConflictError,
    TaskStoreError,
    TaskStoreNotFoundError,
)


class PostgresTaskStore(TaskStore):
    """
    PostgreSQL-backed TaskStore implementation.

    Design goals:
    1. Keep TaskStore as the stable contract for gateway / workers / dispatcher.
    2. Hide ORM/repository details behind a durable store boundary.
    3. Use short-lived sessions per operation to avoid session leakage and
       accidental cross-request state sharing.
    4. Commit on successful mutation and rollback on failure.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        if session_factory is None:
            raise TaskStoreError("session_factory must not be None")
        self._session_factory = session_factory

    async def create(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            try:
                await repo.create(task)
                await session.commit()
                return task
            except TaskRepositoryConflictError as exc:
                await session.rollback()
                raise TaskStoreConflictError(str(exc)) from exc
            except Exception as exc:
                await session.rollback()
                raise TaskStoreError(
                    f"Failed to create task in PostgresTaskStore: task_id={task.task_id}"
                ) from exc

    async def put(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            try:
                await repo.upsert(task)
                await session.commit()
                return task
            except Exception as exc:
                await session.rollback()
                raise TaskStoreError(
                    f"Failed to upsert task in PostgresTaskStore: task_id={task.task_id}"
                ) from exc

    async def get(self, task_id: str) -> Optional[TaskEnvelope]:
        self._validate_task_id(task_id)

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            try:
                return await repo.get(task_id)
            except Exception as exc:
                raise TaskStoreError(
                    f"Failed to get task from PostgresTaskStore: task_id={task_id}"
                ) from exc

    async def update(self, task: TaskEnvelope) -> TaskEnvelope:
        self._validate_task(task)

        async with self._session_factory() as session:
            repo = TaskRepository(session)
            try:
                await repo.update(task)
                await session.commit()
                return task
            except TaskRepositoryNotFoundError as exc:
                await session.rollback()
                raise TaskStoreNotFoundError(str(exc)) from exc
            except Exception as exc:
                await session.rollback()
                raise TaskStoreError(
                    f"Failed to update task in PostgresTaskStore: task_id={task.task_id}"
                ) from exc

    async def exists(self, task_id: str) -> bool:
        self._validate_task_id(task_id)
        task = await self.get(task_id)
        return task is not None

    async def delete(self, task_id: str) -> None:
        self._validate_task_id(task_id)

        async with self._session_factory() as session:
            try:
                record = await session.get(
                    __import__("persistence.models", fromlist=["RuntimeTaskRecord"]).RuntimeTaskRecord,
                    task_id,
                )
                if record is None:
                    raise TaskStoreNotFoundError(f"Task not found for delete: task_id={task_id}")

                await session.delete(record)
                await session.commit()
            except TaskStoreNotFoundError:
                await session.rollback()
                raise
            except Exception as exc:
                await session.rollback()
                raise TaskStoreError(
                    f"Failed to delete task from PostgresTaskStore: task_id={task_id}"
                ) from exc

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