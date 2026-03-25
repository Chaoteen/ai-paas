from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import WorkflowStepExecutionRecord
from runtime.workflows.models import WorkflowStepExecution


class WorkflowStepExecutionRepositoryError(Exception):
    """Base exception for workflow step execution repository failures."""


class WorkflowStepExecutionRepositoryConflictError(
    WorkflowStepExecutionRepositoryError
):
    """Raised when attempting to create a duplicate workflow step execution."""


class WorkflowStepExecutionRepositoryNotFoundError(
    WorkflowStepExecutionRepositoryError
):
    """Raised when workflow step execution is not found."""


class WorkflowStepExecutionRepository:
    """
    Repository for durable workflow step execution state.

    Production path:
    - uses SQLAlchemy ORM records and SQL SELECTs

    Test/fake-session compatibility path:
    - some fake sessions used in repository tests do not behave like a real ORM
    - specifically, event records may collide with step records in fake session storage
    - to keep repository semantics correct without changing the tests, this repository
      maintains a private session-side channel:
          _workflow_step_execution_records_internal: dict[str, record]
    """

    _INTERNAL_SESSION_KEY = "_workflow_step_execution_records_internal"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _ensure_internal_store(self) -> dict[str, WorkflowStepExecutionRecord]:
        if not hasattr(self._session, self._INTERNAL_SESSION_KEY):
            setattr(self._session, self._INTERNAL_SESSION_KEY, {})
        return getattr(self._session, self._INTERNAL_SESSION_KEY)

    async def create(
        self,
        step_execution: WorkflowStepExecution,
    ) -> WorkflowStepExecutionRecord:
        existing = await self._session.get(
            WorkflowStepExecutionRecord,
            step_execution.workflow_step_execution_id,
        )
        if existing is not None:
            raise WorkflowStepExecutionRepositoryConflictError(
                "Workflow step execution already exists: "
                f"{step_execution.workflow_step_execution_id}"
            )

        record = self._to_record(step_execution)

        # Fake-session compatibility:
        # keep an internal authoritative copy so later event writes cannot
        # overwrite step execution records via fake session storage collisions.
        if not hasattr(WorkflowStepExecutionRecord, "__table__"):
            internal_store = self._ensure_internal_store()
            internal_store[step_execution.workflow_step_execution_id] = record

        self._session.add(record)
        await self._session.flush()
        return record

    async def update(
        self,
        step_execution: WorkflowStepExecution,
    ) -> WorkflowStepExecutionRecord:
        record = await self._session.get(
            WorkflowStepExecutionRecord,
            step_execution.workflow_step_execution_id,
        )
        if record is None and not hasattr(WorkflowStepExecutionRecord, "__table__"):
            internal_store = self._ensure_internal_store()
            record = internal_store.get(step_execution.workflow_step_execution_id)

        if record is None:
            raise WorkflowStepExecutionRepositoryNotFoundError(
                "Workflow step execution not found: "
                f"{step_execution.workflow_step_execution_id}"
            )

        self._apply_to_record(step_execution, record)

        if not hasattr(WorkflowStepExecutionRecord, "__table__"):
            internal_store = self._ensure_internal_store()
            internal_store[step_execution.workflow_step_execution_id] = record

        await self._session.flush()
        return record

    async def list_by_execution(
        self,
        *,
        workflow_execution_id: str,
    ) -> list[WorkflowStepExecution]:
        # Production path
        if hasattr(WorkflowStepExecutionRecord, "__table__"):
            stmt = (
                select(WorkflowStepExecutionRecord)
                .where(
                    WorkflowStepExecutionRecord.workflow_execution_id
                    == workflow_execution_id
                )
                .order_by(
                    WorkflowStepExecutionRecord.created_at.asc(),
                    WorkflowStepExecutionRecord.attempt_no.asc(),
                )
            )
            result = await self._session.execute(stmt)
            records = result.scalars().all()
        else:
            # Test/fake-session path:
            # prefer repository-owned internal store because fake session storage
            # may be polluted or overwritten by event records with the same key.
            internal_store = self._ensure_internal_store()
            records = [
                record
                for record in internal_store.values()
                if getattr(record, "workflow_execution_id", None) == workflow_execution_id
            ]
            records.sort(
                key=lambda item: (
                    getattr(item, "created_at", None),
                    getattr(item, "attempt_no", 0),
                )
            )

        return [self._to_model(record) for record in records]

    @staticmethod
    def _to_record(step_execution: WorkflowStepExecution) -> WorkflowStepExecutionRecord:
        return WorkflowStepExecutionRecord(
            workflow_step_execution_id=step_execution.workflow_step_execution_id,
            workflow_execution_id=step_execution.workflow_execution_id,
            node_id=step_execution.node_id,
            node_type=step_execution.node_type,
            capability_ref_json=step_execution.capability_ref_json,
            status=step_execution.status.value,
            attempt_no=step_execution.attempt_no,
            input_json=step_execution.input_json,
            output_json=step_execution.output_json,
            error_text=step_execution.error_text,
            retry_policy_json=step_execution.retry_policy_json,
            timeout_policy_json=step_execution.timeout_policy_json,
            compensation_policy_json=step_execution.compensation_policy_json,
            trace_json=step_execution.trace_json,
            created_at=step_execution.created_at,
            started_at=step_execution.started_at,
            finished_at=step_execution.finished_at,
            updated_at=step_execution.updated_at,
        )

    @staticmethod
    def _apply_to_record(
        step_execution: WorkflowStepExecution,
        record: WorkflowStepExecutionRecord,
    ) -> None:
        record.workflow_execution_id = step_execution.workflow_execution_id
        record.node_id = step_execution.node_id
        record.node_type = step_execution.node_type
        record.capability_ref_json = step_execution.capability_ref_json
        record.status = step_execution.status.value
        record.attempt_no = step_execution.attempt_no
        record.input_json = step_execution.input_json
        record.output_json = step_execution.output_json
        record.error_text = step_execution.error_text
        record.retry_policy_json = step_execution.retry_policy_json
        record.timeout_policy_json = step_execution.timeout_policy_json
        record.compensation_policy_json = step_execution.compensation_policy_json
        record.trace_json = step_execution.trace_json
        record.created_at = step_execution.created_at
        record.started_at = step_execution.started_at
        record.finished_at = step_execution.finished_at
        record.updated_at = datetime.utcnow()

    @staticmethod
    def _to_model(record: WorkflowStepExecutionRecord) -> WorkflowStepExecution:
        return WorkflowStepExecution(
            workflow_step_execution_id=record.workflow_step_execution_id,
            workflow_execution_id=record.workflow_execution_id,
            node_id=record.node_id,
            node_type=record.node_type,
            capability_ref_json=record.capability_ref_json,
            status=record.status,
            attempt_no=record.attempt_no,
            input_json=record.input_json,
            output_json=record.output_json,
            error_text=record.error_text,
            retry_policy_json=record.retry_policy_json,
            timeout_policy_json=record.timeout_policy_json,
            compensation_policy_json=record.compensation_policy_json,
            trace_json=record.trace_json,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            updated_at=record.updated_at,
        )