from __future__ import annotations

from typing import Dict, List, Optional

from .workflow_state import TaskState, WorkflowState


class InMemoryRuntimeStateStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskState] = {}
        self._workflows: Dict[str, WorkflowState] = {}

    async def get_task(self, task_id: str) -> Optional[TaskState]:
        return self._tasks.get(task_id)

    async def save_task(self, task_state: TaskState) -> TaskState:
        self._tasks[task_state.task_id] = task_state
        return task_state

    async def create_task(
        self,
        *,
        task_id: str,
        tenant_id: str,
        workflow_id: str | None = None,
        correlation_id: str | None = None,
        input_payload: dict | None = None,
        metadata: dict | None = None,
    ) -> TaskState:
        existing = self._tasks.get(task_id)
        if existing is not None:
            return existing

        state = TaskState(
            task_id=task_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            input_payload=dict(input_payload or {}),
            metadata=dict(metadata or {}),
        )
        self._tasks[task_id] = state

        if workflow_id:
            workflow = await self.get_or_create_workflow(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
            )
            workflow.add_task(task_id)

        return state

    async def list_tasks(
        self,
        *,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> List[TaskState]:
        items = list(self._tasks.values())

        if tenant_id is not None:
            items = [x for x in items if x.tenant_id == tenant_id]
        if status is not None:
            items = [x for x in items if x.status == status]

        items.sort(key=lambda x: x.created_at)
        return items

    async def transition_task(
        self,
        *,
        task_id: str,
        new_status: str,
        event_type: str | None = None,
        selected_agent_id: str | None = None,
        selected_skill: str | None = None,
        output_payload: dict | None = None,
        error: str | None = None,
        metadata_patch: dict | None = None,
    ) -> TaskState:
        state = self._tasks.get(task_id)
        if state is None:
            raise KeyError(f"Task state not found: {task_id}")

        state.transition_to(
            new_status,
            event_type=event_type,
            selected_agent_id=selected_agent_id,
            selected_skill=selected_skill,
            output_payload=output_payload,
            error=error,
            metadata_patch=metadata_patch,
        )
        self._tasks[task_id] = state
        return state

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        return self._workflows.get(workflow_id)

    async def save_workflow(self, workflow_state: WorkflowState) -> WorkflowState:
        self._workflows[workflow_state.workflow_id] = workflow_state
        return workflow_state

    async def get_or_create_workflow(
        self,
        *,
        workflow_id: str,
        tenant_id: str,
        correlation_id: str | None = None,
        metadata: dict | None = None,
    ) -> WorkflowState:
        existing = self._workflows.get(workflow_id)
        if existing is not None:
            return existing

        state = WorkflowState(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            metadata=dict(metadata or {}),
        )
        self._workflows[workflow_id] = state
        return state

    async def mark_workflow_completed(self, workflow_id: str) -> WorkflowState:
        state = self._workflows.get(workflow_id)
        if state is None:
            raise KeyError(f"Workflow state not found: {workflow_id}")
        state.mark_completed()
        self._workflows[workflow_id] = state
        return state

    async def mark_workflow_failed(
        self,
        workflow_id: str,
        *,
        reason: str | None = None,
    ) -> WorkflowState:
        state = self._workflows.get(workflow_id)
        if state is None:
            raise KeyError(f"Workflow state not found: {workflow_id}")
        state.mark_failed(reason=reason)
        self._workflows[workflow_id] = state
        return state