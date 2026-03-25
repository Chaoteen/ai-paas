from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import WorkflowExecutionRecord
from runtime.workflows.models import WorkflowExecution


class WorkflowExecutionRepositoryError(Exception):
    """Base exception for workflow execution repository failures."""


class WorkflowExecutionRepositoryConflictError(WorkflowExecutionRepositoryError):
    """Raised when attempting to create a duplicate workflow execution."""


class WorkflowExecutionRepositoryNotFoundError(WorkflowExecutionRepositoryError):
    """Raised when workflow execution is not found."""


class WorkflowExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, execution: WorkflowExecution) -> WorkflowExecutionRecord:
        existing = await self._session.get(
            WorkflowExecutionRecord,
            execution.workflow_execution_id,
        )
        if existing is not None:
            raise WorkflowExecutionRepositoryConflictError(
                "Workflow execution already exists: "
                f"{execution.workflow_execution_id}"
            )

        record = self._to_record(execution)
        self._session.add(record)
        await self._session.flush()
        return record

    async def update(self, execution: WorkflowExecution) -> WorkflowExecutionRecord:
        record = await self._session.get(
            WorkflowExecutionRecord,
            execution.workflow_execution_id,
        )
        if record is None:
            raise WorkflowExecutionRepositoryNotFoundError(
                "Workflow execution not found: "
                f"{execution.workflow_execution_id}"
            )

        self._apply_execution_to_record(execution, record)
        await self._session.flush()
        return record

    async def get(
        self,
        workflow_execution_id: str,
    ) -> Optional[WorkflowExecution]:
        record = await self._session.get(
            WorkflowExecutionRecord,
            workflow_execution_id,
        )
        if record is None:
            return None
        return self._to_execution(record)

    async def get_by_task_id(self, task_id: str) -> Optional[WorkflowExecution]:
        stmt = select(WorkflowExecutionRecord).where(
            WorkflowExecutionRecord.task_id == task_id
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._to_execution(record)

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
    ) -> list[WorkflowExecution]:
        stmt = (
            select(WorkflowExecutionRecord)
            .where(WorkflowExecutionRecord.tenant_id == tenant_id)
            .order_by(WorkflowExecutionRecord.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_execution(record) for record in result.scalars().all()]

    @staticmethod
    def _to_record(execution: WorkflowExecution) -> WorkflowExecutionRecord:
        return WorkflowExecutionRecord(
            workflow_execution_id=execution.workflow_execution_id,
            task_id=execution.task_id,
            tenant_id=execution.tenant_id,
            workflow_key=execution.workflow_key,
            workflow_version=execution.workflow_version,
            status=execution.status.value,
            definition_snapshot_json=execution.definition_snapshot_json,
            input_json=execution.input_json,
            context_json=execution.context_json,
            system_context_json=execution.system_context_json,
            output_json=execution.output_json,
            error_text=execution.error_text,
            active_node_ids=execution.active_node_ids,
            resolved_capabilities_json=execution.resolved_capabilities_json,
            governance_json=execution.governance_json,
            trace_json=execution.trace_json,
            created_at=execution.created_at,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            updated_at=execution.updated_at,
        )

    @staticmethod
    def _apply_execution_to_record(
        execution: WorkflowExecution,
        record: WorkflowExecutionRecord,
    ) -> None:
        record.task_id = execution.task_id
        record.tenant_id = execution.tenant_id
        record.workflow_key = execution.workflow_key
        record.workflow_version = execution.workflow_version
        record.status = execution.status.value
        record.definition_snapshot_json = execution.definition_snapshot_json
        record.input_json = execution.input_json
        record.context_json = execution.context_json
        record.system_context_json = execution.system_context_json
        record.output_json = execution.output_json
        record.error_text = execution.error_text
        record.active_node_ids = execution.active_node_ids
        record.resolved_capabilities_json = execution.resolved_capabilities_json
        record.governance_json = execution.governance_json
        record.trace_json = execution.trace_json
        record.created_at = execution.created_at
        record.started_at = execution.started_at
        record.finished_at = execution.finished_at
        record.updated_at = datetime.utcnow()

    @staticmethod
    def _to_execution(record: WorkflowExecutionRecord) -> WorkflowExecution:
        return WorkflowExecution(
            workflow_execution_id=record.workflow_execution_id,
            task_id=record.task_id,
            tenant_id=record.tenant_id,
            workflow_key=record.workflow_key,
            workflow_version=record.workflow_version,
            definition_snapshot_json=record.definition_snapshot_json,
            status=record.status,
            input_json=record.input_json,
            context_json=record.context_json,
            system_context_json=record.system_context_json,
            output_json=record.output_json,
            error_text=record.error_text,
            active_node_ids=record.active_node_ids,
            resolved_capabilities_json=record.resolved_capabilities_json,
            governance_json=record.governance_json,
            trace_json=record.trace_json,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            updated_at=record.updated_at,
        )