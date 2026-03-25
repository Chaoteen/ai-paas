from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.workflow_execution_repository import (
    WorkflowExecutionRepository,
)
from runtime.queue.task_store import get_postgres_session_factory
from runtime.workflows.models import WorkflowExecution

router = APIRouter(tags=["workflow-executions"])


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


async def get_workflow_execution_session_factory() -> Callable[[], AsyncSession]:
    return await get_postgres_session_factory()


def _serialize_execution(execution: WorkflowExecution) -> WorkflowExecutionResponse:
    return WorkflowExecutionResponse(
        workflow_execution_id=execution.workflow_execution_id,
        task_id=execution.task_id,
        tenant_id=execution.tenant_id,
        workflow_key=execution.workflow_key,
        workflow_version=execution.workflow_version,
        status=execution.status.value,
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
        created_at=execution.created_at.isoformat(),
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        finished_at=execution.finished_at.isoformat() if execution.finished_at else None,
        updated_at=execution.updated_at.isoformat(),
    )


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
    async with session_factory() as session:
        repo = WorkflowExecutionRepository(session)
        execution = await repo.get(workflow_execution_id)

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow execution not found: {workflow_execution_id}",
        )

    return _serialize_execution(execution)