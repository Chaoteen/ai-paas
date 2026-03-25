from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from runtime.workflows.models import WorkflowDefinition


class WorkflowRegistryError(Exception):
    """Base exception for workflow registry failures."""


class WorkflowDefinitionNotFoundError(WorkflowRegistryError):
    """Raised when a requested workflow definition cannot be found."""


class WorkflowRegistry:
    async def get_definition(
        self,
        *,
        workflow_key: str,
        workflow_version: Optional[str] = None,
    ) -> WorkflowDefinition:
        raise NotImplementedError


class PostgresWorkflowRegistry(WorkflowRegistry):
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        if session_factory is None:
            raise WorkflowRegistryError("session_factory must not be None")
        self._session_factory = session_factory

    async def get_definition(
        self,
        *,
        workflow_key: str,
        workflow_version: Optional[str] = None,
    ) -> WorkflowDefinition:
        async with self._session_factory() as session:
            repo = WorkflowDefinitionRepository(session)

            if workflow_version:
                definition = await repo.get(
                    workflow_key=workflow_key,
                    workflow_version=workflow_version,
                )
            else:
                definition = await repo.get_active(workflow_key=workflow_key)

            if definition is None:
                if workflow_version:
                    raise WorkflowDefinitionNotFoundError(
                        f"Workflow definition not found: {workflow_key}:{workflow_version}"
                    )
                raise WorkflowDefinitionNotFoundError(
                    f"Active workflow definition not found: {workflow_key}"
                )

            return definition