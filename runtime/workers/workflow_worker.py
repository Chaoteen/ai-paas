from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import get_postgres_session_factory
from runtime.workflow_runtime_service import WorkflowRuntimeService
from runtime.workers.worker_base import WorkerBase
from runtime.workflows.registry import PostgresWorkflowRegistry


class WorkflowWorker(WorkerBase):
    """
    Queue worker for workflow start requests.

    Current role:
    - consume workflow_tasks stream
    - resolve workflow definition
    - materialize durable workflow execution / step / event records
    - return a structured orchestration-accepted result payload

    This keeps WorkerBase contract unchanged while moving workflow orchestration
    onto a formal runtime service.
    """

    stream_name = "workflow_tasks"
    group_name = "workflow_workers"

    def __init__(
        self,
        *,
        queue: Any,
        store: Any,
        consumer_name: str,
        service: Optional[WorkflowRuntimeService] = None,
    ) -> None:
        super().__init__(
            queue=queue,
            store=store,
            consumer_name=consumer_name,
        )
        self._service = service

    async def execute_task(self, task: TaskEnvelope) -> Dict[str, Any]:
        service = await self._get_service()
        return await service.run(task)

    async def _get_service(self) -> WorkflowRuntimeService:
        if self._service is not None:
            return self._service

        session_factory: Callable[[], AsyncSession] = await get_postgres_session_factory()
        registry = PostgresWorkflowRegistry(session_factory=session_factory)
        self._service = WorkflowRuntimeService(
            session_factory=session_factory,
            registry=registry,
        )
        return self._service