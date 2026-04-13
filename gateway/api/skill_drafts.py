from __future__ import annotations

from collections.abc import Callable
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
from persistence.repositories.skill_draft_repository import SkillDraftRepository
from runtime.queue.task_store import get_postgres_session_factory
from runtime.skills.dialogue_distillation_service import DialogueDistillationService
from runtime.skills.draft_service import SkillDraftService
from runtime.skills.errors import (
    InvalidPatchError,
    InvalidStateTransitionError,
    NotFoundError,
)
from runtime.skills.event_service import RecordingEventService
from runtime.skills.session_service import RecordingSessionService

router = APIRouter(tags=["skill-drafts"])


async def get_session_factory() -> Callable[[], AsyncSession]:
    return await get_postgres_session_factory()


class SkillDraftWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recording_session_id: Optional[str] = None
    previous_skill_draft_id: Optional[str] = None
    draft_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    intent_summary: Optional[str] = None
    distillation_source_type: str
    input_schema_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )
    output_schema_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )
    draft_definition_json: dict[str, Any]
    distillation_notes_json: dict[str, Any] = Field(default_factory=dict)
    execution_binding_json: dict[str, Any]
    derived_from_json: dict[str, Any]
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class SkillDraftPatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    intent_summary: Optional[str] = None
    input_schema_json: Optional[dict[str, Any]] = None
    output_schema_json: Optional[dict[str, Any]] = None
    draft_definition_json: Optional[dict[str, Any]] = None
    distillation_notes_json: Optional[dict[str, Any]] = None
    execution_binding_json: Optional[dict[str, Any]] = None
    derived_from_json: Optional[dict[str, Any]] = None
    metadata_json: Optional[dict[str, Any]] = None


class DialogueDistillationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recording_session_id: Optional[str] = None
    session_title: str = Field(..., min_length=1)
    draft_name: str = Field(..., min_length=1)
    draft_key: Optional[str] = None
    intent_summary: Optional[str] = None
    dialogue_turns: list[dict[str, Any]] = Field(default_factory=list)

    input_schema_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )
    output_schema_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )
    draft_definition_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "draft_type": "task_skill",
            "steps": [],
            "inputs": [],
            "outputs": [],
            "guardrails": {},
            "hints": {},
        }
    )
    execution_binding_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "binding_type": "unbound",
            "target_ref": {"object_type": None, "object_id": None},
            "config_json": {},
        }
    )
    metadata_json: dict[str, Any] = Field(default_factory=dict)


def _serialize_draft(item) -> dict[str, Any]:
    body = item.model_dump(mode="json")
    body["status"] = item.status.value
    body["distillation_source_type"] = item.distillation_source_type.value
    body["input_schema_json"] = item.input_schema.model_dump(mode="json")
    body["output_schema_json"] = item.output_schema.model_dump(mode="json")
    body["draft_definition_json"] = item.draft_definition.model_dump(mode="json")
    body["execution_binding_json"] = item.execution_binding.model_dump(mode="json")
    body["derived_from_json"] = item.derived_from.model_dump(mode="json")
    return body


def _serialize_session(item) -> dict[str, Any]:
    body = item.model_dump(mode="json")
    body["source_type"] = item.source_type.value
    body["status"] = item.status.value
    body["distillation_mode"] = item.distillation_mode.value
    body["current_phase"] = item.current_phase.value
    return body


@router.post("/skill-drafts", status_code=status.HTTP_201_CREATED)
async def create_skill_draft(
    request: SkillDraftWriteRequest,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = SkillDraftService(
            session_repo=RecordingSessionRepository(session),
            draft_repo=SkillDraftRepository(session),
        )
        try:
            item = await service.create_draft(
                tenant_id=ctx.tenant_id,
                recording_session_id=request.recording_session_id,
                previous_skill_draft_id=request.previous_skill_draft_id,
                draft_key=request.draft_key,
                name=request.name,
                intent_summary=request.intent_summary,
                distillation_source_type=request.distillation_source_type,
                input_schema_json=request.input_schema_json,
                output_schema_json=request.output_schema_json,
                draft_definition_json=request.draft_definition_json,
                distillation_notes_json=request.distillation_notes_json,
                execution_binding_json=request.execution_binding_json,
                derived_from_json=request.derived_from_json,
                metadata_json=request.metadata_json,
                actor_user_id=ctx.user_id,
            )
            await session.commit()
            return _serialize_draft(item)
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/skill-drafts/distill-from-dialogue", status_code=status.HTTP_201_CREATED)
async def distill_skill_draft_from_dialogue(
    request: DialogueDistillationRequest,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        session_repo = RecordingSessionRepository(session)
        event_repo = RecordingActionEventRepository(session)
        draft_repo = SkillDraftRepository(session)

        distillation_service = DialogueDistillationService(
            session_service=RecordingSessionService(session_repo=session_repo),
            event_service=RecordingEventService(
                session_repo=session_repo,
                event_repo=event_repo,
            ),
            draft_service=SkillDraftService(
                session_repo=session_repo,
                draft_repo=draft_repo,
            ),
        )
        try:
            result = await distillation_service.distill_from_dialogue(
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.user_id,
                session_title=request.session_title,
                draft_name=request.draft_name,
                intent_summary=request.intent_summary,
                dialogue_turns=request.dialogue_turns,
                recording_session_id=request.recording_session_id,
                draft_key=request.draft_key,
                input_schema_json=request.input_schema_json,
                output_schema_json=request.output_schema_json,
                draft_definition_json=request.draft_definition_json,
                execution_binding_json=request.execution_binding_json,
                metadata_json=request.metadata_json,
            )
            await session.commit()
            return {
                "recording_session": _serialize_session(result["recording_session"]),
                "skill_draft": _serialize_draft(result["skill_draft"]),
                "dialogue_turn_count": result["dialogue_turn_count"],
            }
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skill-drafts")
async def list_skill_drafts(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    recording_session_id: Optional[str] = Query(default=None),
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = SkillDraftService(
            session_repo=RecordingSessionRepository(session),
            draft_repo=SkillDraftRepository(session),
        )
        items = await service.list_drafts(
            tenant_id=ctx.tenant_id,
            status=status_filter,
            recording_session_id=recording_session_id,
        )
        return {"items": [_serialize_draft(item) for item in items]}


@router.get("/skill-drafts/{skill_draft_id}")
async def get_skill_draft(
    skill_draft_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = SkillDraftService(
            session_repo=RecordingSessionRepository(session),
            draft_repo=SkillDraftRepository(session),
        )
        try:
            item = await service.get_draft(
                tenant_id=ctx.tenant_id,
                skill_draft_id=skill_draft_id,
            )
            return _serialize_draft(item)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/skill-drafts/{skill_draft_id}")
async def patch_skill_draft(
    skill_draft_id: str,
    request: SkillDraftPatchRequest,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    async with session_factory() as session:
        service = SkillDraftService(
            session_repo=RecordingSessionRepository(session),
            draft_repo=SkillDraftRepository(session),
        )
        try:
            item = await service.patch_draft(
                tenant_id=ctx.tenant_id,
                skill_draft_id=skill_draft_id,
                patch={k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None},
                actor_user_id=ctx.user_id,
            )
            await session.commit()
            return _serialize_draft(item)
        except InvalidPatchError as exc:
            await session.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _transition_draft(
    *,
    skill_draft_id: str,
    action: str,
    ctx: PlatformRequestContext,
    session_factory: Callable[[], AsyncSession],
):
    async with session_factory() as session:
        service = SkillDraftService(
            session_repo=RecordingSessionRepository(session),
            draft_repo=SkillDraftRepository(session),
        )
        try:
            item = await service.transition_status(
                tenant_id=ctx.tenant_id,
                skill_draft_id=skill_draft_id,
                action=action,
                actor_user_id=ctx.user_id,
            )
            await session.commit()
            return _serialize_draft(item)
        except InvalidStateTransitionError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except NotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/skill-drafts/{skill_draft_id}/submit-review")
async def submit_review(
    skill_draft_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_draft(
        skill_draft_id=skill_draft_id,
        action="submit_review",
        ctx=ctx,
        session_factory=session_factory,
    )


@router.post("/skill-drafts/{skill_draft_id}/accept")
async def accept_skill_draft(
    skill_draft_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_draft(
        skill_draft_id=skill_draft_id,
        action="accept",
        ctx=ctx,
        session_factory=session_factory,
    )


@router.post("/skill-drafts/{skill_draft_id}/reject")
async def reject_skill_draft(
    skill_draft_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_draft(
        skill_draft_id=skill_draft_id,
        action="reject",
        ctx=ctx,
        session_factory=session_factory,
    )


@router.post("/skill-drafts/{skill_draft_id}/archive")
async def archive_skill_draft(
    skill_draft_id: str,
    ctx: PlatformRequestContext = Depends(get_platform_request_context),
    session_factory: Callable[[], AsyncSession] = Depends(get_session_factory),
):
    return await _transition_draft(
        skill_draft_id=skill_draft_id,
        action="archive",
        ctx=ctx,
        session_factory=session_factory,
    )