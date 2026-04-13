from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from runtime.skills.errors import InvalidPatchError, InvalidStateTransitionError, NotFoundError
from runtime.skills.models import (
    RecordingSession,
    RecordingSessionDistillationMode,
    RecordingSessionPhase,
    RecordingSessionSourceType,
    RecordingSessionStatus,
)


@dataclass
class RecordingSessionService:
    session_repo: object

    async def create_session(
        self,
        *,
        tenant_id: str,
        source_type: str,
        distillation_mode: str,
        title: str,
        description: Optional[str],
        context_json: dict,
        source_metadata_json: dict,
        actor_user_id: Optional[str],
    ) -> RecordingSession:
        session = RecordingSession(
            recording_session_id=f"rec_{uuid4().hex}",
            tenant_id=tenant_id,
            source_type=RecordingSessionSourceType(source_type),
            status=RecordingSessionStatus.DRAFT,
            distillation_mode=RecordingSessionDistillationMode(distillation_mode),
            current_phase=RecordingSessionPhase.CAPTURE,
            title=title,
            description=description,
            context_json=context_json or {},
            source_metadata_json=source_metadata_json or {},
            latest_skill_draft_id=None,
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        return await self.session_repo.create(session)

    async def get_session(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
    ) -> RecordingSession:
        session = await self.session_repo.get_by_id(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )
        if session is None:
            raise NotFoundError(f"recording session not found: {recording_session_id}")
        return session

    async def list_sessions(
        self,
        *,
        tenant_id: str,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> list[RecordingSession]:
        return await self.session_repo.list_by_tenant(
            tenant_id=tenant_id,
            status=status,
            source_type=source_type,
        )

    async def patch_session(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        patch: dict,
        actor_user_id: Optional[str],
    ) -> RecordingSession:
        forbidden = {
            "recording_session_id",
            "tenant_id",
            "status",
            "latest_skill_draft_id",
            "created_at",
            "created_by",
        }
        invalid = forbidden.intersection(patch.keys())
        if invalid:
            raise InvalidPatchError(
                f"recording session patch contains forbidden fields: {sorted(invalid)}"
            )

        session = await self.get_session(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )

        next_data = session.model_dump(mode="python")
        next_data.update(patch)
        next_data["updated_by"] = actor_user_id
        next_data["updated_at"] = datetime.utcnow()

        updated = RecordingSession.model_validate(next_data)
        return await self.session_repo.update_mutable_fields(updated)

    async def transition_status(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        action: str,
        actor_user_id: Optional[str],
    ) -> RecordingSession:
        session = await self.get_session(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )

        transitions = {
            RecordingSessionStatus.DRAFT: {
                "start_collecting": (
                    RecordingSessionStatus.COLLECTING,
                    RecordingSessionPhase.CAPTURE,
                ),
                "archive": (
                    RecordingSessionStatus.ARCHIVED,
                    RecordingSessionPhase.REVIEW,
                ),
            },
            RecordingSessionStatus.COLLECTING: {
                "mark_distilled": (
                    RecordingSessionStatus.DISTILLED,
                    RecordingSessionPhase.DISTILL,
                ),
                "archive": (
                    RecordingSessionStatus.ARCHIVED,
                    RecordingSessionPhase.REVIEW,
                ),
            },
            RecordingSessionStatus.DISTILLED: {
                "archive": (
                    RecordingSessionStatus.ARCHIVED,
                    RecordingSessionPhase.REVIEW,
                ),
            },
            RecordingSessionStatus.ARCHIVED: {},
        }

        next_tuple = transitions[session.status].get(action)
        if next_tuple is None:
            raise InvalidStateTransitionError(
                f"invalid recording session transition: {session.status.value} -> {action}"
            )

        next_status, next_phase = next_tuple
        updated = session.model_copy(
            update={
                "status": next_status,
                "current_phase": next_phase,
                "updated_by": actor_user_id,
                "updated_at": datetime.utcnow(),
            }
        )
        return await self.session_repo.transition_status(updated)

    async def set_latest_skill_draft_pointer(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        skill_draft_id: str,
        actor_user_id: Optional[str],
    ) -> None:
        await self.get_session(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )
        await self.session_repo.set_latest_skill_draft_id(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
            skill_draft_id=skill_draft_id,
            actor_user_id=actor_user_id,
        )