from __future__ import annotations

from typing import Any, Dict, Optional, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from runtime.queue.task_models import (
    AgentTaskPayload,
    GenerationTaskPayload,
    TaskEnvelope,
)
from runtime.queue.task_store import (
    TaskStore,
    get_postgres_session_factory,
    get_task_store,
)
from runtime.queue.task_submission_service import (
    TaskSubmissionConflictError,
    TaskSubmissionService,
    TaskSubmissionServiceError,
)

router = APIRouter(tags=["tasks"])


class AgentSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_id", "prompt", "model")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class GenerationSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    size: Optional[str] = None
    duration_seconds: Optional[int] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_id", "prompt", "model")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str
    queue_name: str
    stream_name: str
    durable: bool = True
    outbox_event_id: int


class TaskGetResponse(BaseModel):
    task_id: str
    tenant_id: str
    task_type: str
    queue_name: str
    status: str
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    retry_count: int
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None


async def get_task_submission_service() -> TaskSubmissionService:
    session_factory: Callable[[], AsyncSession] = await get_postgres_session_factory()
    return TaskSubmissionService(session_factory=session_factory)


def _serialize_task(task: TaskEnvelope) -> TaskGetResponse:
    return TaskGetResponse(
        task_id=task.task_id,
        tenant_id=task.tenant_id,
        task_type=task.task_type.value,
        queue_name=task.queue_name,
        status=task.status.value,
        payload=task.payload,
        result=task.result,
        error=task.error,
        created_at=task.created_at.isoformat(),
        queued_at=task.queued_at.isoformat() if task.queued_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        finished_at=task.finished_at.isoformat() if task.finished_at else None,
        retry_count=task.retry_count,
        correlation_id=task.correlation_id,
        idempotency_key=task.idempotency_key,
    )


@router.post(
    "/agent/submit",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_agent_task(
    request: AgentSubmitRequest,
    submission_service: TaskSubmissionService = Depends(get_task_submission_service),
) -> TaskSubmitResponse:
    payload = AgentTaskPayload(
        prompt=request.prompt,
        model=request.model,
        system_prompt=request.system_prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        metadata=request.metadata,
    )

    task = TaskEnvelope.for_agent(
        tenant_id=request.tenant_id,
        payload=payload,
        queue_name="agent_tasks",
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
    )

    try:
        result = await submission_service.submit_task(
            task=task,
            stream_name="agent_tasks",
        )
    except TaskSubmissionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate agent task submission: {exc}",
        ) from exc
    except TaskSubmissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to durably submit agent task: {exc}",
        ) from exc

    return TaskSubmitResponse(
        task_id=result.task_id,
        status=result.status,
        queue_name=result.queue_name,
        stream_name=result.stream_name,
        durable=True,
        outbox_event_id=result.outbox_event_id,
    )


@router.post(
    "/generation/image/submit",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_image_generation_task(
    request: GenerationSubmitRequest,
    submission_service: TaskSubmissionService = Depends(get_task_submission_service),
) -> TaskSubmitResponse:
    payload = GenerationTaskPayload(
        prompt=request.prompt,
        model=request.model,
        modality="image",
        size=request.size,
        duration_seconds=request.duration_seconds,
        metadata=request.metadata,
    )

    task = TaskEnvelope.for_generation(
        tenant_id=request.tenant_id,
        payload=payload,
        queue_name="generation_tasks",
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
    )

    try:
        result = await submission_service.submit_task(
            task=task,
            stream_name="generation_tasks",
        )
    except TaskSubmissionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate image generation submission: {exc}",
        ) from exc
    except TaskSubmissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to durably submit image generation task: {exc}",
        ) from exc

    return TaskSubmitResponse(
        task_id=result.task_id,
        status=result.status,
        queue_name=result.queue_name,
        stream_name=result.stream_name,
        durable=True,
        outbox_event_id=result.outbox_event_id,
    )


@router.post(
    "/generation/video/submit",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_video_generation_task(
    request: GenerationSubmitRequest,
    submission_service: TaskSubmissionService = Depends(get_task_submission_service),
) -> TaskSubmitResponse:
    payload = GenerationTaskPayload(
        prompt=request.prompt,
        model=request.model,
        modality="video",
        size=request.size,
        duration_seconds=request.duration_seconds,
        metadata=request.metadata,
    )

    task = TaskEnvelope.for_generation(
        tenant_id=request.tenant_id,
        payload=payload,
        queue_name="generation_tasks",
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
    )

    try:
        result = await submission_service.submit_task(
            task=task,
            stream_name="generation_tasks",
        )
    except TaskSubmissionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate video generation submission: {exc}",
        ) from exc
    except TaskSubmissionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to durably submit video generation task: {exc}",
        ) from exc

    return TaskSubmitResponse(
        task_id=result.task_id,
        status=result.status,
        queue_name=result.queue_name,
        stream_name=result.stream_name,
        durable=True,
        outbox_event_id=result.outbox_event_id,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskGetResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task(
    task_id: str,
    store: TaskStore = Depends(get_task_store),
) -> TaskGetResponse:
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    return _serialize_task(task)