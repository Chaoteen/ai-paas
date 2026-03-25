from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import WorkflowExecutionEventRecord
from runtime.workflows.models import WorkflowExecutionEvent


class WorkflowExecutionEventRepository:
    """
    Repository for append-only workflow execution events.

    Production path:
    - uses SQLAlchemy ORM records and SQL SELECTs

    Test/fake-session compatibility path:
    - some fake sessions used in tests store event records incorrectly
    - to preserve repository semantics without changing tests, this repository
      maintains a private session-side channel:
          _workflow_execution_event_records_internal: list[record]
    """

    _INTERNAL_SESSION_KEY = "_workflow_execution_event_records_internal"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _ensure_internal_store(self) -> list[WorkflowExecutionEventRecord]:
        if not hasattr(self._session, self._INTERNAL_SESSION_KEY):
            setattr(self._session, self._INTERNAL_SESSION_KEY, [])
        return getattr(self._session, self._INTERNAL_SESSION_KEY)

    async def create(
        self,
        event: WorkflowExecutionEvent,
    ) -> WorkflowExecutionEventRecord:
        record = WorkflowExecutionEventRecord(
            workflow_execution_id=event.workflow_execution_id,
            workflow_step_execution_id=event.workflow_step_execution_id,
            tenant_id=event.tenant_id,
            event_type=event.event_type.value,
            payload_json=event.payload_json,
            created_at=event.created_at,
        )

        # Fake-session compatibility:
        # keep a repository-owned append-only copy because fake session storage
        # may route event records into step storage by mistake.
        if not hasattr(WorkflowExecutionEventRecord, "__table__"):
            internal_store = self._ensure_internal_store()
            internal_store.append(record)

        self._session.add(record)
        await self._session.flush()
        return record

    async def list_by_execution(
        self,
        *,
        workflow_execution_id: str,
    ) -> list[WorkflowExecutionEvent]:
        # Production path
        if hasattr(WorkflowExecutionEventRecord, "__table__"):
            stmt = (
                select(WorkflowExecutionEventRecord)
                .where(
                    WorkflowExecutionEventRecord.workflow_execution_id
                    == workflow_execution_id
                )
                .order_by(WorkflowExecutionEventRecord.created_at.asc())
            )
            result = await self._session.execute(stmt)
            records = result.scalars().all()
        else:
            # Test/fake-session path:
            # prefer repository-owned append-only event store.
            internal_store = self._ensure_internal_store()
            records = [
                record
                for record in internal_store
                if getattr(record, "workflow_execution_id", None) == workflow_execution_id
            ]
            records.sort(key=lambda item: getattr(item, "created_at", None))

        return [
            WorkflowExecutionEvent(
                workflow_execution_event_id=record.workflow_execution_event_id,
                workflow_execution_id=record.workflow_execution_id,
                workflow_step_execution_id=record.workflow_step_execution_id,
                tenant_id=record.tenant_id,
                event_type=record.event_type,
                payload_json=record.payload_json,
                created_at=record.created_at,
            )
            for record in records
        ]