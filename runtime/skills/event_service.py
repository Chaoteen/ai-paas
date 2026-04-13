from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from runtime.skills.errors import NotFoundError
from runtime.skills.models import (
    RecordingActionActorType,
    RecordingActionEvent,
    RecordingActionEventType,
)


@dataclass
class RecordingEventService:
    session_repo: object
    event_repo: object

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
        session = await self.session_repo.get_by_id(
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

        event = RecordingActionEvent(
            recording_action_event_id=f"evt_{uuid4().hex}",
            recording_session_id=recording_session_id,
            tenant_id=tenant_id,
            sequence_no=0,
            idempotency_key=idempotency_key,
            source_event_id=source_event_id,
            event_timestamp=event_timestamp,
            event_type=RecordingActionEventType(event_type),
            actor_type=RecordingActionActorType(actor_type),
            payload_json=payload_json or {},
            source_ref_json=source_ref_json or {},
            metadata_json=metadata_json or {},
        )
        return await self.event_repo.append_with_allocated_sequence(event)

    async def list_events(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
    ) -> list[RecordingActionEvent]:
        session = await self.session_repo.get_by_id(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )
        if session is None:
            raise NotFoundError(f"recording session not found: {recording_session_id}")

        return await self.event_repo.list_by_session(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
        )

    async def get_event_by_idempotency_key(
        self,
        *,
        tenant_id: str,
        recording_session_id: str,
        idempotency_key: str,
    ) -> Optional[RecordingActionEvent]:
        return await self.event_repo.get_by_idempotency_key(
            tenant_id=tenant_id,
            recording_session_id=recording_session_id,
            idempotency_key=idempotency_key,
        )