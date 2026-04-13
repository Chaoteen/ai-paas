from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import RecordingActionEventRecord, RecordingSessionRecord
from runtime.skills.models import RecordingActionEvent


class RecordingActionEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(record: RecordingActionEventRecord) -> RecordingActionEvent:
        return RecordingActionEvent(
            recording_action_event_id=record.recording_action_event_id,
            recording_session_id=record.recording_session_id,
            tenant_id=record.tenant_id,
            sequence_no=record.sequence_no,
            idempotency_key=record.idempotency_key,
            source_event_id=record.source_event_id,
            event_timestamp=record.event_timestamp,
            event_type=record.event_type,
            actor_type=record.actor_type,
            payload_json=record.payload_json or {},
            source_ref_json=record.source_ref_json or {},
            metadata_json=record.metadata_json or {},
            created_at=record.created_at,
        )

    async def get_by_idempotency_key(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        idempotency_key: str,
    ) -> Optional[RecordingActionEvent]:
        stmt = select(RecordingActionEventRecord).where(
            RecordingActionEventRecord.tenant_id == tenant_id,
            RecordingActionEventRecord.recording_session_id == recording_session_id,
            RecordingActionEventRecord.idempotency_key == idempotency_key,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def append_with_allocated_sequence(
        self,
        item: RecordingActionEvent,
    ) -> RecordingActionEvent:
        lock_stmt = (
            select(RecordingSessionRecord)
            .where(
                RecordingSessionRecord.recording_session_id == item.recording_session_id,
                RecordingSessionRecord.tenant_id == item.tenant_id,
            )
            .with_for_update()
        )
        lock_row = (await self._session.execute(lock_stmt)).scalar_one_or_none()
        if lock_row is None:
            raise ValueError("recording session not found when appending action event")

        seq_stmt = select(func.max(RecordingActionEventRecord.sequence_no)).where(
            RecordingActionEventRecord.tenant_id == item.tenant_id,
            RecordingActionEventRecord.recording_session_id == item.recording_session_id,
        )
        current = (await self._session.execute(seq_stmt)).scalar_one()
        next_sequence_no = int(current or 0) + 1

        record = RecordingActionEventRecord(
            recording_action_event_id=item.recording_action_event_id,
            recording_session_id=item.recording_session_id,
            tenant_id=item.tenant_id,
            sequence_no=next_sequence_no,
            idempotency_key=item.idempotency_key,
            source_event_id=item.source_event_id,
            event_timestamp=item.event_timestamp,
            event_type=item.event_type.value,
            actor_type=item.actor_type.value,
            payload_json=item.payload_json,
            source_ref_json=item.source_ref_json,
            metadata_json=item.metadata_json,
            created_at=item.created_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def list_by_session(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
    ) -> list[RecordingActionEvent]:
        stmt = (
            select(RecordingActionEventRecord)
            .where(
                RecordingActionEventRecord.tenant_id == tenant_id,
                RecordingActionEventRecord.recording_session_id == recording_session_id,
            )
            .order_by(RecordingActionEventRecord.sequence_no.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]