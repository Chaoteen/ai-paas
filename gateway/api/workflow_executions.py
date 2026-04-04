from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.workflow_execution_event_repository import (
    WorkflowExecutionEventRepository,
)
from persistence.repositories.workflow_execution_repository import (
    WorkflowExecutionRepository,
)
from persistence.repositories.workflow_step_execution_repository import (
    WorkflowStepExecutionRepository,
)
from runtime.queue.task_store import get_postgres_session_factory
from runtime.workflows.models import (
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowStepExecution,
)

router = APIRouter(tags=["workflow-executions"])


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


class WorkflowExecutionResponse(BaseModel):
    workflow_execution_id: str
    task_id: str
    tenant_id: str
    workflow_key: str
    workflow_version: str
    status: str
    definition_snapshot_json: Dict[str, Any]
    input_json: Dict[str, Any]
    context_json: Dict[str, Any]
    system_context_json: Dict[str, Any]
    output_json: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None
    active_node_ids: list[str]
    resolved_capabilities_json: Dict[str, Any]
    governance_json: Dict[str, Any]
    trace_json: Dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: str


class WorkflowExecutionListResponse(BaseModel):
    items: list[WorkflowExecutionResponse]
    total: int


class WorkflowStepExecutionResponse(BaseModel):
    workflow_step_execution_id: str
    workflow_execution_id: str
    node_id: str
    node_type: str
    capability_ref_json: Dict[str, Any]
    status: str
    attempt_no: int
    input_json: Dict[str, Any]
    output_json: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None
    retry_policy_json: Dict[str, Any]
    timeout_policy_json: Dict[str, Any]
    compensation_policy_json: Dict[str, Any]
    trace_json: Dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: str


class WorkflowExecutionStepsResponse(BaseModel):
    items: list[WorkflowStepExecutionResponse]
    total: int


class WorkflowExecutionEventResponse(BaseModel):
    workflow_execution_event_id: int
    workflow_execution_id: str
    workflow_step_execution_id: Optional[str] = None
    tenant_id: str
    event_type: str
    payload_json: Dict[str, Any]
    created_at: str


class WorkflowExecutionEventsResponse(BaseModel):
    items: list[WorkflowExecutionEventResponse]
    total: int


class WorkflowExecutionTimelineItemResponse(BaseModel):
    sequence_no: int
    created_at: str
    lane: str
    event_type: str
    workflow_step_execution_id: Optional[str] = None
    node_id: Optional[str] = None
    status: Optional[str] = None
    payload_json: Dict[str, Any]


class WorkflowExecutionTimelineResponse(BaseModel):
    workflow_execution_id: str
    items: list[WorkflowExecutionTimelineItemResponse]
    total: int


class WorkflowExecutionDetailResponse(BaseModel):
    execution: WorkflowExecutionResponse
    steps: list[WorkflowStepExecutionResponse]
    events: list[WorkflowExecutionEventResponse]
    timeline: list[WorkflowExecutionTimelineItemResponse]
    summary: Dict[str, Any]


async def get_workflow_execution_session_factory() -> Callable[[], AsyncSession]:
    return await get_postgres_session_factory()


def _serialize_execution(execution: WorkflowExecution) -> WorkflowExecutionResponse:
    return WorkflowExecutionResponse(
        workflow_execution_id=execution.workflow_execution_id,
        task_id=execution.task_id,
        tenant_id=execution.tenant_id,
        workflow_key=execution.workflow_key,
        workflow_version=execution.workflow_version,
        status=_enum_value(execution.status),
        definition_snapshot_json=execution.definition_snapshot_json,
        input_json=execution.input_json,
        context_json=execution.context_json,
        system_context_json=execution.system_context_json,
        output_json=execution.output_json,
        error_text=execution.error_text,
        active_node_ids=execution.active_node_ids,
        resolved_capabilities_json=execution.resolved_capabilities_json,
        governance_json=execution.governance_json,
        trace_json=execution.trace_json,
        created_at=_iso(execution.created_at) or "",
        started_at=_iso(execution.started_at),
        finished_at=_iso(execution.finished_at),
        updated_at=_iso(execution.updated_at) or "",
    )


def _serialize_step(step: WorkflowStepExecution) -> WorkflowStepExecutionResponse:
    return WorkflowStepExecutionResponse(
        workflow_step_execution_id=step.workflow_step_execution_id,
        workflow_execution_id=step.workflow_execution_id,
        node_id=step.node_id,
        node_type=step.node_type,
        capability_ref_json=step.capability_ref_json,
        status=_enum_value(step.status),
        attempt_no=step.attempt_no,
        input_json=step.input_json,
        output_json=step.output_json,
        error_text=step.error_text,
        retry_policy_json=step.retry_policy_json,
        timeout_policy_json=step.timeout_policy_json,
        compensation_policy_json=step.compensation_policy_json,
        trace_json=step.trace_json,
        created_at=_iso(step.created_at) or "",
        started_at=_iso(step.started_at),
        finished_at=_iso(step.finished_at),
        updated_at=_iso(step.updated_at) or "",
    )


def _serialize_event(event: WorkflowExecutionEvent) -> WorkflowExecutionEventResponse:
    return WorkflowExecutionEventResponse(
        workflow_execution_event_id=event.workflow_execution_event_id,
        workflow_execution_id=event.workflow_execution_id,
        workflow_step_execution_id=event.workflow_step_execution_id,
        tenant_id=event.tenant_id,
        event_type=_enum_value(event.event_type),
        payload_json=event.payload_json,
        created_at=_iso(event.created_at) or "",
    )


def _build_timeline(
    *,
    workflow_execution_id: str,
    events: list[WorkflowExecutionEvent],
) -> WorkflowExecutionTimelineResponse:
    items: list[WorkflowExecutionTimelineItemResponse] = []
    for index, event in enumerate(events, start=1):
        payload = event.payload_json or {}
        node_id = payload.get("node_id")
        status_value = payload.get("status")

        items.append(
            WorkflowExecutionTimelineItemResponse(
                sequence_no=index,
                created_at=_iso(event.created_at) or "",
                lane="step" if event.workflow_step_execution_id else "execution",
                event_type=_enum_value(event.event_type),
                workflow_step_execution_id=event.workflow_step_execution_id,
                node_id=node_id,
                status=status_value,
                payload_json=payload,
            )
        )

    return WorkflowExecutionTimelineResponse(
        workflow_execution_id=workflow_execution_id,
        items=items,
        total=len(items),
    )


async def _load_execution_or_404(
    *,
    session_factory: Callable[[], AsyncSession],
    workflow_execution_id: str,
) -> WorkflowExecution:
    async with session_factory() as session:
        repo = WorkflowExecutionRepository(session)
        execution = await repo.get(workflow_execution_id)
        if execution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow execution not found: {workflow_execution_id}",
            )
        return execution


@router.get(
    "/workflow/executions/by-task/{task_id}",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_workflow_execution_by_task(
    task_id: str,
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionResponse:
    async with session_factory() as session:
        repo = WorkflowExecutionRepository(session)
        execution = await repo.get_by_task_id(task_id)
        if execution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow execution not found by task_id: {task_id}",
            )
        return _serialize_execution(execution)


@router.get(
    "/workflow/executions/{workflow_execution_id}",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_workflow_execution(
    workflow_execution_id: str,
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionResponse:
    execution = await _load_execution_or_404(
        session_factory=session_factory,
        workflow_execution_id=workflow_execution_id,
    )
    return _serialize_execution(execution)


@router.get(
    "/workflow/executions",
    response_model=WorkflowExecutionListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_workflow_executions_by_tenant(
    tenant_id: str = Query(..., min_length=1),
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionListResponse:
    async with session_factory() as session:
        repo = WorkflowExecutionRepository(session)
        items = await repo.list_by_tenant(tenant_id=tenant_id)
        serialized = [_serialize_execution(item) for item in items]
        return WorkflowExecutionListResponse(items=serialized, total=len(serialized))


@router.get(
    "/workflow/executions/{workflow_execution_id}/steps",
    response_model=WorkflowExecutionStepsResponse,
    status_code=status.HTTP_200_OK,
)
async def list_workflow_execution_steps(
    workflow_execution_id: str,
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionStepsResponse:
    await _load_execution_or_404(
        session_factory=session_factory,
        workflow_execution_id=workflow_execution_id,
    )

    async with session_factory() as session:
        repo = WorkflowStepExecutionRepository(session)
        items = await repo.list_by_execution(
            workflow_execution_id=workflow_execution_id
        )
        serialized = [_serialize_step(item) for item in items]
        return WorkflowExecutionStepsResponse(items=serialized, total=len(serialized))


@router.get(
    "/workflow/executions/{workflow_execution_id}/events",
    response_model=WorkflowExecutionEventsResponse,
    status_code=status.HTTP_200_OK,
)
async def list_workflow_execution_events(
    workflow_execution_id: str,
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionEventsResponse:
    await _load_execution_or_404(
        session_factory=session_factory,
        workflow_execution_id=workflow_execution_id,
    )

    async with session_factory() as session:
        repo = WorkflowExecutionEventRepository(session)
        items = await repo.list_by_execution(
            workflow_execution_id=workflow_execution_id
        )
        serialized = [_serialize_event(item) for item in items]
        return WorkflowExecutionEventsResponse(items=serialized, total=len(serialized))


@router.get(
    "/workflow/executions/{workflow_execution_id}/timeline",
    response_model=WorkflowExecutionTimelineResponse,
    status_code=status.HTTP_200_OK,
)
async def get_workflow_execution_timeline(
    workflow_execution_id: str,
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionTimelineResponse:
    await _load_execution_or_404(
        session_factory=session_factory,
        workflow_execution_id=workflow_execution_id,
    )

    async with session_factory() as session:
        repo = WorkflowExecutionEventRepository(session)
        events = await repo.list_by_execution(workflow_execution_id=workflow_execution_id)
        return _build_timeline(
            workflow_execution_id=workflow_execution_id,
            events=events,
        )


@router.get(
    "/workflow/executions/{workflow_execution_id}/detail",
    response_model=WorkflowExecutionDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_workflow_execution_detail(
    workflow_execution_id: str,
    session_factory: Callable[[], AsyncSession] = Depends(
        get_workflow_execution_session_factory
    ),
) -> WorkflowExecutionDetailResponse:
    execution = await _load_execution_or_404(
        session_factory=session_factory,
        workflow_execution_id=workflow_execution_id,
    )

    async with session_factory() as session:
        step_repo = WorkflowStepExecutionRepository(session)
        event_repo = WorkflowExecutionEventRepository(session)

        step_items = await step_repo.list_by_execution(
            workflow_execution_id=workflow_execution_id
        )
        event_items = await event_repo.list_by_execution(
            workflow_execution_id=workflow_execution_id
        )

    serialized_execution = _serialize_execution(execution)
    serialized_steps = [_serialize_step(item) for item in step_items]
    serialized_events = [_serialize_event(item) for item in event_items]
    timeline = _build_timeline(
        workflow_execution_id=workflow_execution_id,
        events=event_items,
    )

    summary = {
        "workflow_execution_id": workflow_execution_id,
        "task_id": execution.task_id,
        "tenant_id": execution.tenant_id,
        "workflow_key": execution.workflow_key,
        "workflow_version": execution.workflow_version,
        "execution_status": _enum_value(execution.status),
        "step_count": len(serialized_steps),
        "event_count": len(serialized_events),
        "active_node_ids": execution.active_node_ids,
        "has_error": execution.error_text is not None,
    }

    return WorkflowExecutionDetailResponse(
        execution=serialized_execution,
        steps=serialized_steps,
        events=serialized_events,
        timeline=timeline.items,
        summary=summary,
    )