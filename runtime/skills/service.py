from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from runtime.skills.contracts import ExecutionBindingContract
from runtime.skills.models import (
    RecordingActionActorType,
    RecordingActionEvent,
    RecordingActionEventType,
    RecordingSession,
    RecordingSessionStatus,
    SkillDraft,
    SkillDraftStatus,
)


class SkillDistillationServiceError(Exception):
    pass


class InvalidStateTransitionError(SkillDistillationServiceError):
    pass


class InvalidPatchError(SkillDistillationServiceError):
    pass


class NotFoundError(SkillDistillationServiceError):
    pass


class ConflictError(SkillDistillationServiceError):
    pass


@dataclass
class SkillDistillationService:
    session_repo: object
    event_repo: object
    draft_repo: object

    async def create_session(
        self,
        *,
        tenant_id: str,
        source_type: str,
        title: str,
        description: Optional[str],
        context_json: dict,
        source_metadata_json: dict,
        actor_user_id: Optional[str],
    ) -> RecordingSession:
        session = RecordingSession(
            recording_session_id=f"rec_{uuid4().hex}",
            tenant_id=tenant_id,
            source_type=source_type,
            status=RecordingSessionStatus.DRAFT,
            title=title,
            description=description,
            context_json=context_json or {},
            source_metadata_json=source_metadata_json or {},
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        return await self.session_repo.create(session)

    async def patch_session(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        patch: dict,
        actor_user_id: Optional[str],
    ) -> RecordingSession:
        forbidden = {
            "status",
            "latest_skill_draft_id",
            "recording_session_id",
            "tenant_id",
            "created_at",
        }
        invalid = forbidden.intersection(patch.keys())
        if invalid:
            raise InvalidPatchError(
                f"session patch contains forbidden fields: {sorted(invalid)}"
            )

        session = await self.session_repo.get(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )
        if session is None:
            raise NotFoundError(f"recording session not found: {recording_session_id}")

        next_data = session.model_dump(mode="python")
        next_data.update(patch)
        next_data["updated_by"] = actor_user_id
        next_data["updated_at"] = datetime.utcnow()

        updated = RecordingSession.model_validate(next_data)
        return await self.session_repo.update(updated)

    async def transition_session(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        action: str,
        actor_user_id: Optional[str],
    ) -> RecordingSession:
        session = await self.session_repo.get(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )
        if session is None:
            raise NotFoundError(f"recording session not found: {recording_session_id}")

        allowed = {
            RecordingSessionStatus.DRAFT.value: {
                "start_collecting": RecordingSessionStatus.COLLECTING,
                "archive": RecordingSessionStatus.ARCHIVED,
            },
            RecordingSessionStatus.COLLECTING.value: {
                "mark_distilled": RecordingSessionStatus.DISTILLED,
                "archive": RecordingSessionStatus.ARCHIVED,
            },
            RecordingSessionStatus.DISTILLED.value: {
                "archive": RecordingSessionStatus.ARCHIVED,
            },
            RecordingSessionStatus.ARCHIVED.value: {},
        }

        next_status = allowed[session.status.value].get(action)
        if next_status is None:
            raise InvalidStateTransitionError(
                f"invalid session transition: {session.status.value} -> {action}"
            )

        updated = session.model_copy(
            update={
                "status": next_status,
                "updated_by": actor_user_id,
                "updated_at": datetime.utcnow(),
            }
        )
        return await self.session_repo.update(updated)

    async def append_event(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        idempotency_key: Optional[str],
        source_event_id: Optional[str],
        event_timestamp,
        event_type: str,
        actor_type: str,
        payload_json: dict,
        source_ref_json: dict,
        metadata_json: dict,
    ) -> RecordingActionEvent:
        session = await self.session_repo.get(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )
        if session is None:
            raise NotFoundError(f"recording session not found: {recording_session_id}")

        if idempotency_key:
            existing = await self.event_repo.get_by_idempotency_key(
                tenant_id=tenant_id,
                recording_session_id=recording_session_id,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return existing

        next_sequence_no = await self.event_repo.next_sequence_no(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )

        event = RecordingActionEvent(
            recording_action_event_id=f"evt_{uuid4().hex}",
            recording_session_id=recording_session_id,
            tenant_id=tenant_id,
            sequence_no=next_sequence_no,
            idempotency_key=idempotency_key,
            source_event_id=source_event_id,
            event_timestamp=event_timestamp,
            event_type=RecordingActionEventType(event_type),
            actor_type=RecordingActionActorType(actor_type),
            payload_json=payload_json or {},
            source_ref_json=source_ref_json or {},
            metadata_json=metadata_json or {},
        )
        return await self.event_repo.create(event)

    async def create_draft(
        self,
        *,
        tenant_id: str,
        recording_session_id: Optional[str],
        draft_key: str,
        name: str,
        intent_summary: Optional[str],
        distillation_source_type: str,
        input_schema_json: dict,
        output_schema_json: dict,
        draft_definition_json: dict,
        distillation_notes_json: dict,
        execution_binding_json: dict,
        derived_from_json: dict,
        metadata_json: dict,
        actor_user_id: Optional[str],
    ) -> SkillDraft:
        if recording_session_id is not None:
            session = await self.session_repo.get(
                tenant_id=tenant_id,
                recording_session_id=recording_session_id,
            )
            if session is None:
                raise NotFoundError(f"recording session not found: {recording_session_id}")

        ExecutionBindingContract.model_validate(execution_binding_json)

        draft_version = await self.draft_repo.allocate_next_draft_version(
            tenant_id=tenant_id,
            draft_key=draft_key,
        )

        draft = SkillDraft(
            skill_draft_id=f"sd_{uuid4().hex}",
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
            draft_key=draft_key,
            draft_version=draft_version,
            status=SkillDraftStatus.DRAFT,
            name=name,
            intent_summary=intent_summary,
            distillation_source_type=distillation_source_type,
            input_schema_json=input_schema_json or {},
            output_schema_json=output_schema_json or {},
            draft_definition_json=draft_definition_json or {},
            distillation_notes_json=distillation_notes_json or {},
            execution_binding_json=execution_binding_json,
            derived_from_json=derived_from_json or {},
            metadata_json=metadata_json or {},
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )

        created = await self.draft_repo.create(draft)

        if recording_session_id is not None:
            await self.session_repo.set_latest_skill_draft_id(
                tenant_id=tenant_id,
                recording_session_id=recording_session_id,
                skill_draft_id=created.skill_draft_id,
                actor_user_id=actor_user_id,
            )

        return created

    async def patch_draft(
        self,
        *,
        tenant_id: str,
        skill_draft_id: str,
        patch: dict,
        actor_user_id: Optional[str],
    ) -> SkillDraft:
        forbidden = {
            "status",
            "draft_version",
            "recording_session_id",
            "tenant_id",
            "created_at",
            "skill_draft_id",
            "distillation_source_type",
        }
        invalid = forbidden.intersection(patch.keys())
        if invalid:
            raise InvalidPatchError(
                f"draft patch contains forbidden fields: {sorted(invalid)}"
            )

        draft = await self.draft_repo.get(
            tenant_id=tenant_id,
            skill_draft_id=skill_draft_id,
        )
        if draft is None:
            raise NotFoundError(f"skill draft not found: {skill_draft_id}")

        next_data = draft.model_dump(mode="python")
        next_data.update(patch)
        next_data["updated_by"] = actor_user_id
        next_data["updated_at"] = datetime.utcnow()

        if "execution_binding_json" in patch:
            ExecutionBindingContract.model_validate(next_data["execution_binding_json"])

        updated = SkillDraft.model_validate(next_data)
        return await self.draft_repo.update(updated)

    async def transition_draft(
        self,
        *,
        tenant_id: str,
        skill_draft_id: str,
        action: str,
        actor_user_id: Optional[str],
    ) -> SkillDraft:
        draft = await self.draft_repo.get(
            tenant_id=tenant_id,
            skill_draft_id=skill_draft_id,
        )
        if draft is None:
            raise NotFoundError(f"skill draft not found: {skill_draft_id}")

        allowed = {
            SkillDraftStatus.DRAFT.value: {
                "submit_review": SkillDraftStatus.REVIEWING,
            },
            SkillDraftStatus.REVIEWING.value: {
                "accept": SkillDraftStatus.ACCEPTED,
                "reject": SkillDraftStatus.REJECTED,
            },
            SkillDraftStatus.ACCEPTED.value: {
                "archive": SkillDraftStatus.ARCHIVED,
            },
            SkillDraftStatus.REJECTED.value: {
                "restore_draft": SkillDraftStatus.DRAFT,
                "archive": SkillDraftStatus.ARCHIVED,
            },
            SkillDraftStatus.ARCHIVED.value: {},
        }

        next_status = allowed[draft.status.value].get(action)
        if next_status is None:
            raise InvalidStateTransitionError(
                f"invalid draft transition: {draft.status.value} -> {action}"
            )

        updated = draft.model_copy(
            update={
                "status": next_status,
                "updated_by": actor_user_id,
                "updated_at": datetime.utcnow(),
            }
        )
        return await self.draft_repo.update(updated)