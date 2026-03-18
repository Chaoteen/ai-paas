from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runtime.queue.task_models import (
    AgentTaskPayload,
    GenerationTaskKind,
    GenerationTaskPayload,
    TaskEnvelope,
    TaskPriority,
)
from runtime.queue.task_store import get_task_store

router = APIRouter(tags=["tasks"])


class AgentSubmitRequest(BaseModel):
    agent_id: str
    input: Any

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None

    routing_policy: Optional[str] = None
    required_capability: Optional[str] = None
    requested_capabilities: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    secrets_scope: list[str] = Field(default_factory=list)
    workspace_root: Optional[str] = None
    preferred_skill: Optional[str] = None

    priority: TaskPriority = TaskPriority.NORMAL
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationImageSubmitRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    routing_policy: Optional[str] = None

    width: Optional[int] = 1024
    height: Optional[int] = 1024
    seed: Optional[int] = None
    count: int = 1

    quality: Optional[str] = None
    style: Optional[str] = None

    priority: TaskPriority = TaskPriority.NORMAL
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationVideoSubmitRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    routing_policy: Optional[str] = None

    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: int = 5
    fps: Optional[int] = None
    seed: Optional[int] = None
    count: int = 1
    resolution: Optional[str] = "720p"

    priority: TaskPriority = TaskPriority.NORMAL
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskSubmitResponse(BaseModel):
    success: bool
    task_id: str
    task_type: str
    status: str
    queue_name: str
    priority: str


class TaskReadResponse(BaseModel):
    success: bool
    task: Dict[str, Any]


@router.post("/agent/submit", response_model=TaskSubmitResponse)
async def submit_agent_task(request: AgentSubmitRequest):
    payload = AgentTaskPayload(
        agent_id=request.agent_id,
        input=request.input,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        session_id=request.session_id,
        workflow_id=request.workflow_id,
        correlation_id=request.correlation_id,
        routing_policy=request.routing_policy,
        required_capability=request.required_capability,
        requested_capabilities=list(request.requested_capabilities),
        allowed_capabilities=list(request.allowed_capabilities),
        secrets_scope=list(request.secrets_scope),
        workspace_root=request.workspace_root,
        preferred_skill=request.preferred_skill,
        metadata=dict(request.metadata),
    )

    task = TaskEnvelope.new_agent_task(
        payload,
        priority=request.priority,
        queue_name="agent",
        metadata={"submit_source": "gateway.api.tasks"},
    )
    task.mark_queued()

    store = get_task_store()
    store.put(task)

    return TaskSubmitResponse(
        success=True,
        task_id=task.task_id,
        task_type=task.task_type.value,
        status=task.status.value,
        queue_name=task.queue_name,
        priority=task.priority.value,
    )


@router.post("/generation/image/submit", response_model=TaskSubmitResponse)
async def submit_generation_image_task(request: GenerationImageSubmitRequest):
    payload = GenerationTaskPayload(
        kind=GenerationTaskKind.IMAGE,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        provider=request.provider,
        model=request.model,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        workflow_id=request.workflow_id,
        correlation_id=request.correlation_id,
        routing_policy=request.routing_policy,
        width=request.width,
        height=request.height,
        seed=request.seed,
        count=request.count,
        quality=request.quality,
        style=request.style,
        metadata=dict(request.metadata),
    )

    task = TaskEnvelope.new_generation_task(
        payload,
        priority=request.priority,
        queue_name="generation",
        metadata={"submit_source": "gateway.api.tasks"},
    )
    task.mark_queued()

    store = get_task_store()
    store.put(task)

    return TaskSubmitResponse(
        success=True,
        task_id=task.task_id,
        task_type=task.task_type.value,
        status=task.status.value,
        queue_name=task.queue_name,
        priority=task.priority.value,
    )


@router.post("/generation/video/submit", response_model=TaskSubmitResponse)
async def submit_generation_video_task(request: GenerationVideoSubmitRequest):
    payload = GenerationTaskPayload(
        kind=GenerationTaskKind.VIDEO,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        provider=request.provider,
        model=request.model,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        workflow_id=request.workflow_id,
        correlation_id=request.correlation_id,
        routing_policy=request.routing_policy,
        width=request.width,
        height=request.height,
        duration_seconds=request.duration_seconds,
        fps=request.fps,
        seed=request.seed,
        count=request.count,
        resolution=request.resolution,
        metadata=dict(request.metadata),
    )

    task = TaskEnvelope.new_generation_task(
        payload,
        priority=request.priority,
        queue_name="generation",
        metadata={"submit_source": "gateway.api.tasks"},
    )
    task.mark_queued()

    store = get_task_store()
    store.put(task)

    return TaskSubmitResponse(
        success=True,
        task_id=task.task_id,
        task_type=task.task_type.value,
        status=task.status.value,
        queue_name=task.queue_name,
        priority=task.priority.value,
    )


@router.get("/tasks/{task_id}", response_model=TaskReadResponse)
async def get_task(task_id: str):
    store = get_task_store()
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskReadResponse(
        success=True,
        task=task.to_dict(),
    )