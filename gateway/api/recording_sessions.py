from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.dependencies.platform_context import (
    PlatformRequestContext,
    get_platform_request_context,
)
from persistence.repositories.recording_action_event_repository import (
    RecordingActionEventRepository,
)
from persistence.repositories.recording_session_repository import (
    RecordingSessionRepository,
)
from runtime.queue.task_store import get_postgres_session_factory
from runtime.skills.errors import (
    InvalidPatchError,
    InvalidStateTransitionError,
    NotFoundError,
)
from runtime.skills.event_service import RecordingEventService
from runtime.skills.session_service import RecordingSessionService

router = APIRouter(tags=["recording-sessions"])


async def get_session_factory() -> Callable[[], AsyncSession]:
    return await get_postgres_session_factory()


class RecordingSessionWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    distillation_mode: str = "dialogue_only"
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    context_json: dict[str, Any] = Field(default_factory=dict)
    source_metadata_json: dict[str, Any] = Field(default_factory=dict)


class RecordingSessionPatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    distillation_mode: Optional[str] = None
    current_phase: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    context_json: Optional[dict[str, Any]] = None
    source_metadata_json: Optional[dict[str, Any]] = None


class RecordingActionEventWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: Optional[str] = None
    source_event_id: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    event_type: str
    actor_type: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    source_ref_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


def _serialize_session(item) -> dict[str, Any]:
    body = item.model_dump(mode="json")
    body["source_type"] = item.source_type.value
    body["status"] = item.status.value
    body["distillation_mode"] = item.distillation_mode.value
    body["current_phase"] = item.current_phase.value
    return body


def _serialize_event(item) -> dict[str, Any]:
    body = item.model_dump(mode="json")
    body["event_type"] = item.event_type.value
    body["actor_type"] = item.actor_type.value
    return body


@router.post("/recording/sessions", status_code=status.HTTP_201_CREATED)
async def create_recording_session(
    request: RecordingSessionWriteRequest,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = RecordingSessionService(
            session_repo=RecordingSessionRepository(session),
        )
        item = await service.create_session(
            tenant_id=ctx.tenant_id,
            source_type=request.source_type,
            distillation_mode=request.distillation_mode,
            title=request.title,
            description=request.description,
            context_json=request.context_json,
            source_metadata_json=request.source_metadata_json,
            actor_user_id=ctx.user_id,
        )
        await session.commit()
        return _serialize_session(item)


@router.get("/recording/sessions")
async def list_recording_sessions(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    source_type: Optional[str] = Query(default=None),
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = RecordingSessionService(
            session_repo=RecordingSessionRepository(session),
        )
        items = await service.list_sessions(
            tenant_id=ctx.tenant_id,
            status=status_filter,
            source_type=source_type,
        )
        return {"items": [_serialize_session(item) for item in items]}


@router.get("/recording/sessions/{recording_session_id}")
async def get_recording_session(
    recording_session_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = RecordingSessionService(
            session_repo=RecordingSessionRepository(session),
        )
        try:
            item = await service.get_session(
                tenant_id=ctx.tenant_id,
                recording_session_id=recording_session_id,
            )
            return _serialize_session(item)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/recording/sessions/{recording_session_id}")
async def patch_recording_session(
    recording_session_id: str,
    request: RecordingSessionPatchRequest,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = RecordingSessionService(
            session_repo=RecordingSessionRepository(session),
        )
        try:
            item = await service.patch_session(
                tenant_id=ctx.tenant_id,
                recording_session_id=recording_session_id,
                patch={k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None},
                actor_user_id=ctx.user_id,
            )
            await session.commit()
            return _serialize_session(item)
        except InvalidPatchError as exc:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/recording/sessions/{recording_session_id}/events", status_code=status.HTTP_201_CREATED)
async def append_recording_event(
    recording_session_id: str,
    request: RecordingActionEventWriteRequest,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = RecordingEventService(
            session_repo=RecordingSessionRepository(session),
            event_repo=RecordingActionEventRepository(session),
        )
        try:
            item = await service.append_event(
                tenant_id=ctx.tenant_id,
                recording_session_id=recording_session_id,
                idempotency_key=request.idempotency_key,
                source_event_id=request.source_event_id,
                event_timestamp=request.event_timestamp,
                event_type=request.event_type,
                actor_type=request.actor_type,
                payload_json=request.payload_json,
                source_ref_json=request.source_ref_json,
                metadata_json=request.metadata_json,
            )
            await session.commit()
            return _serialize_event(item)
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/recording/sessions/{recording_session_id}/events")
async def list_recording_events(
    recording_session_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = RecordingEventService(
            session_repo=RecordingSessionRepository(session),
            event_repo=RecordingActionEventRepository(session),
        )
        try:
            items = await service.list_events(
                tenant_id=ctx.tenant_id,
                recording_session_id=recording_session_id,
            )
            return {"items": [_serialize_event(item) for item in items]}
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _transition_session(
    *,
    recording_session_id: str,
    action: str,
    ctx: PlatformRequestContext,
    session_factory: Callable[[], AsyncSession],
):
    async with session_factory() as session:
        service = RecordingSessionService(
            session_repo=RecordingSessionRepository(session),
        )
        try:
            item = await service.transition_status(
                tenant_id=ctx.tenant_id,
                recording_session_id=recording_session_id,
                action=action,
                actor_user_id=ctx.user_id,
            )
            await session.commit()
            return _serialize_session(item)
        except InvalidStateTransitionError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/recording/sessions/{recording_session_id}/start-collecting")
async def start_collecting(
    recording_session_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_session(
        recording_session_id=recording_session_id,
        action="start_collecting",
        ctx=ctx,
        session_factory=session_factory,
    )


@router.post("/recording/sessions/{recording_session_id}/mark-distilled")
async def mark_distilled(
    recording_session_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_session(
        recording_session_id=recording_session_id,
        action="mark_distilled",
        ctx=ctx,
        session_factory=session_factory,
    )


@router.post("/recording/sessions/{recording_session_id}/archive")
async def archive_recording_session(
    recording_session_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_session(
        recording_session_id=recording_session_id,
        action="archive",
        ctx=ctx,
        session_factory=session_factory,
    )