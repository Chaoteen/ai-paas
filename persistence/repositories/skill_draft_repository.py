from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import SkillDraftRecord
from runtime.skills.models import SkillDraft


class SkillDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(record: SkillDraftRecord) -> SkillDraft:
        payload = {
            "skill_draft_id": record.skill_draft_id,
            "tenant_id": record.tenant_id,
            "recording_session_id": record.recording_session_id,
            "previous_skill_draft_id": record.previous_skill_draft_id,
            "promoted_skill_id": record.promoted_skill_id,
            "promoted_skill_version_id": record.promoted_skill_version_id,
            "draft_key": record.draft_key,
            "draft_version": record.draft_version,
            "status": record.status,
            "name": record.name,
            "intent_summary": record.intent_summary,
            "distillation_source_type": record.distillation_source_type,
            "input_schema_json": record.input_schema_json or {},
            "output_schema_json": record.output_schema_json or {},
            "draft_definition_json": record.draft_definition_json or {},
            "distillation_notes_json": record.distillation_notes_json or {},
            "execution_binding_json": record.execution_binding_json or {},
            "derived_from_json": record.derived_from_json or {},
            "metadata_json": record.metadata_json or {},
            "created_by": record.created_by,
            "updated_by": record.updated_by,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        return SkillDraft.from_persistence_payload(payload)

    async def create(self, item: SkillDraft) -> SkillDraft:
        payload = item.to_persistence_payload()
        record = SkillDraftRecord(
            skill_draft_id=payload["skill_draft_id"],
            tenant_id=payload["tenant_id"],
            recording_session_id=payload["recording_session_id"],
            previous_skill_draft_id=payload["previous_skill_draft_id"],
            promoted_skill_id=payload["promoted_skill_id"],
            promoted_skill_version_id=payload["promoted_skill_version_id"],
            draft_key=payload["draft_key"],
            draft_version=payload["draft_version"],
            status=payload["status"],
            name=payload["name"],
            intent_summary=payload["intent_summary"],
            distillation_source_type=payload["distillation_source_type"],
            input_schema_json=payload["input_schema_json"],
            output_schema_json=payload["output_schema_json"],
            draft_definition_json=payload["draft_definition_json"],
            distillation_notes_json=payload["distillation_notes_json"],
            execution_binding_json=payload["execution_binding_json"],
            derived_from_json=payload["derived_from_json"],
            metadata_json=payload["metadata_json"],
            created_by=payload["created_by"],
            updated_by=payload["updated_by"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
        )
        self._session.add(record)
        await self._session.flush()
        return self._to_domain(record)

    async def get_by_id(
        self,
        *,
        tenant_id: str,
        skill_draft_id: str,
    ) -> Optional[SkillDraft]:
        record = await self._session.get(SkillDraftRecord, skill_draft_id)
        if record is None or record.tenant_id != tenant_id:
            return None
        return self._to_domain(record)

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
        status: Optional[str] = None,
        recording_session_id: Optional[str] = None,
    ) -> list[SkillDraft]:
        stmt = select(SkillDraftRecord).where(SkillDraftRecord.tenant_id == tenant_id)

        if status:
            stmt = stmt.where(SkillDraftRecord.status == status)
        if recording_session_id:
            stmt = stmt.where(SkillDraftRecord.recording_session_id == recording_session_id)

        stmt = stmt.order_by(SkillDraftRecord.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def allocate_next_version(
        self,
        *,
        tenant_id: str,
        draft_key: str,
    ) -> str:
        stmt = select(SkillDraftRecord.draft_version).where(
            SkillDraftRecord.tenant_id == tenant_id,
            SkillDraftRecord.draft_key == draft_key,
        )
        versions = (await self._session.execute(stmt)).scalars().all()

        max_no = 0
        for version in versions:
            match = re.fullmatch(r"v(\d+)", version or "")
            if match:
                max_no = max(max_no, int(match.group(1)))
        return f"v{max_no + 1}"

    async def update_mutable_fields(self, item: SkillDraft) -> SkillDraft:
        record = await self._session.get(SkillDraftRecord, item.skill_draft_id)
        if record is None or record.tenant_id != item.tenant_id:
            raise ValueError("skill draft not found")

        payload = item.to_persistence_payload()

        record.name = payload["name"]
        record.intent_summary = payload["intent_summary"]
        record.input_schema_json = payload["input_schema_json"]
        record.output_schema_json = payload["output_schema_json"]
        record.draft_definition_json = payload["draft_definition_json"]
        record.distillation_notes_json = payload["distillation_notes_json"]
        record.execution_binding_json = payload["execution_binding_json"]
        record.derived_from_json = payload["derived_from_json"]
        record.metadata_json = payload["metadata_json"]
        record.updated_by = payload["updated_by"]
        record.updated_at = payload["updated_at"]

        await self._session.flush()
        return self._to_domain(record)

    async def transition_status(self, item: SkillDraft) -> SkillDraft:
        record = await self._session.get(SkillDraftRecord, item.skill_draft_id)
        if record is None or record.tenant_id != item.tenant_id:
            raise ValueError("skill draft not found")

        record.status = item.status.value
        record.updated_by = item.updated_by
        record.updated_at = item.updated_at

        await self._session.flush()
        return self._to_domain(record)