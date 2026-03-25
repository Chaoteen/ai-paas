from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
    WorkflowDefinitionRepositoryConflictError,
)
from runtime.queue.task_store import get_postgres_session_factory
from runtime.workflows.models import (
    WorkflowDefinition,
    WorkflowDefinitionStatus,
)

router = APIRouter(tags=["workflow-definitions"])


class WorkflowDefinitionWriteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_key: str = Field(..., min_length=1)
    workflow_version: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    status: str = Field(default=WorkflowDefinitionStatus.DRAFT.value)

    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    nodes: list[Dict[str, Any]] = Field(default_factory=list)
    edges: list[Dict[str, Any]] = Field(default_factory=list)
    policies: Dict[str, Any] = Field(default_factory=dict)
    governance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    checksum: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @field_validator("workflow_key", "workflow_version", "display_name", "status")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class WorkflowDefinitionResponse(BaseModel):
    workflow_key: str
    workflow_version: str
    display_name: str
    status: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    nodes: list[Dict[str, Any]]
    edges: list[Dict[str, Any]]
    policies: Dict[str, Any]
    governance: Dict[str, Any]
    metadata: Dict[str, Any]
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: str
    updated_at: str


async def get_workflow_session_factory() -> Callable[[], AsyncSession]:
    return await get_postgres_session_factory()


def _serialize_definition(definition: WorkflowDefinition) -> WorkflowDefinitionResponse:
    data = definition.model_dump(mode="json")
    data["status"] = definition.status.value
    data["created_at"] = definition.created_at.isoformat()
    data["updated_at"] = definition.updated_at.isoformat()
    return WorkflowDefinitionResponse(**data)


@router.post(
    "/workflow/definitions",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_definition(
    request: WorkflowDefinitionWriteRequest,
    session_factory: Callable[[], AsyncSession] = Depends(get_workflow_session_factory),
) -> WorkflowDefinitionResponse:
    definition = WorkflowDefinition.model_validate(request.model_dump(mode="json"))

    async with session_factory() as session:
        repo = WorkflowDefinitionRepository(session)
        try:
            await repo.create(definition)
            await session.commit()
        except WorkflowDefinitionRepositoryConflictError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except Exception:
            await session.rollback()
            raise

    return _serialize_definition(definition)


@router.get(
    "/workflow/definitions/{workflow_key}/active",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_active_workflow_definition(
    workflow_key: str,
    session_factory: Callable[[], AsyncSession] = Depends(get_workflow_session_factory),
) -> WorkflowDefinitionResponse:
    async with session_factory() as session:
        repo = WorkflowDefinitionRepository(session)
        definition = await repo.get_active(workflow_key=workflow_key)

    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active workflow definition not found: {workflow_key}",
        )

    return _serialize_definition(definition)


@router.get(
    "/workflow/definitions/{workflow_key}/{workflow_version}",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_workflow_definition(
    workflow_key: str,
    workflow_version: str,
    session_factory: Callable[[], AsyncSession] = Depends(get_workflow_session_factory),
) -> WorkflowDefinitionResponse:
    async with session_factory() as session:
        repo = WorkflowDefinitionRepository(session)
        definition = await repo.get(
            workflow_key=workflow_key,
            workflow_version=workflow_version,
        )

    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow definition not found: {workflow_key}:{workflow_version}",
        )

    return _serialize_definition(definition)