from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import RecordingSessionRecord
from runtime.skills.models import RecordingSession


class RecordingSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(record: RecordingSessionRecord) -> RecordingSession:
        return RecordingSession(
            recording_session_id=record.recording_session_id,
            tenant_id=record.tenant_id,
            source_type=record.source_type,
            status=record.status,
            distillation_mode=record.distillation_mode,
            current_phase=record.current_phase,
            title=record.title,
            description=record.description,
            context_json=record.context_json or {},
            source_metadata_json=record.source_metadata_json or {},
            latest_skill_draft_id=record.latest_skill_draft_id,
            created_by=record.created_by,
            updated_by=record.updated_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def create(self, item: RecordingSession) -> RecordingSession:
        record = RecordingSessionRecord(
            recording_session_id=item.recording_session_id,
            tenant_id=item.tenant_id,
            source_type=item.source_type.value,
            status=item.status.value,
            distillation_mode=item.distillation_mode.value,
            current_phase=item.current_phase.value,
            title=item.title,
            description=item.description,
            context_json=item.context_json,
            source_metadata_json=item.source_metadata_json,
            latest_skill_draft_id=item.latest_skill_draft_id,
            created_by=item.created_by,
            updated_by=item.updated_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def get_by_id(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
    ) -> Optional[RecordingSession]:
        record = await self._session.get(RecordingSessionRecord, recording_session_id)
        if record is None or record.tenant_id != tenant_id:
            return None
        return self._to_domain(record)

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> list[RecordingSession]:
        stmt = select(RecordingSessionRecord).where(
            RecordingSessionRecord.tenant_id == tenant_id
        )
        if status:
            stmt = stmt.where(RecordingSessionRecord.status == status)
        if source_type:
            stmt = stmt.where(RecordingSessionRecord.source_type == source_type)
        stmt = stmt.order_by(RecordingSessionRecord.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def update_mutable_fields(self, item: RecordingSession) -> RecordingSession:
        record = await self._session.get(RecordingSessionRecord, item.recording_session_id)
        if record is None or record.tenant_id != item.tenant_id:
            raise ValueError("recording session not found")

        record.distillation_mode = item.distillation_mode.value
        record.current_phase = item.current_phase.value
        record.title = item.title
        record.description = item.description
        record.context_json = item.context_json
        record.source_metadata_json = item.source_metadata_json
        record.updated_by = item.updated_by
        record.updated_at = item.updated_at

        await self._session.flush()
        return self._to_domain(record)

    async def transition_status(self, item: RecordingSession) -> RecordingSession:
        record = await self._session.get(RecordingSessionRecord, item.recording_session_id)
        if record is None or record.tenant_id != item.tenant_id:
            raise ValueError("recording session not found")

        record.status = item.status.value
        record.current_phase = item.current_phase.value
        record.updated_by = item.updated_by
        record.updated_at = item.updated_at

        await self._session.flush()
        return self._to_domain(record)

    async def set_latest_skill_draft_id(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        skill_draft_id: str,
        actor_user_id: Optional[str],
    ) -> None:
        record = await self._session.get(RecordingSessionRecord, recording_session_id)
        if record is None or record.tenant_id != tenant_id:
            raise ValueError("recording session not found")

        record.latest_skill_draft_id = skill_draft_id
        record.updated_by = actor_user_id

        await self._session.flush()