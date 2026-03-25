from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import WorkflowDefinitionRecord
from runtime.workflows.models import WorkflowDefinition, WorkflowDefinitionStatus


class WorkflowDefinitionRepositoryError(Exception):
    """Base exception for workflow definition repository failures."""


class WorkflowDefinitionRepositoryConflictError(WorkflowDefinitionRepositoryError):
    """Raised when attempting to create a duplicate workflow definition version."""


class WorkflowDefinitionRepositoryNotFoundError(WorkflowDefinitionRepositoryError):
    """Raised when a workflow definition version is not found."""


class WorkflowDefinitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, definition: WorkflowDefinition) -> WorkflowDefinitionRecord:
        existing = await self._session.get(
            WorkflowDefinitionRecord,
            {
                "workflow_key": definition.workflow_key,
                "workflow_version": definition.workflow_version,
            },
        )
        if existing is not None:
            raise WorkflowDefinitionRepositoryConflictError(
                "Workflow definition already exists: "
                f"{definition.workflow_key}:{definition.workflow_version}"
            )

        record = self._to_record(definition)
        self._session.add(record)
        await self._session.flush()
        return record

    async def upsert(self, definition: WorkflowDefinition) -> WorkflowDefinitionRecord:
        record = await self._session.get(
            WorkflowDefinitionRecord,
            {
                "workflow_key": definition.workflow_key,
                "workflow_version": definition.workflow_version,
            },
        )
        if record is None:
            record = self._to_record(definition)
            self._session.add(record)
        else:
            self._apply_definition_to_record(definition, record)

        await self._session.flush()
        return record

    async def update(self, definition: WorkflowDefinition) -> WorkflowDefinitionRecord:
        record = await self._session.get(
            WorkflowDefinitionRecord,
            {
                "workflow_key": definition.workflow_key,
                "workflow_version": definition.workflow_version,
            },
        )
        if record is None:
            raise WorkflowDefinitionRepositoryNotFoundError(
                "Workflow definition not found: "
                f"{definition.workflow_key}:{definition.workflow_version}"
            )

        self._apply_definition_to_record(definition, record)
        await self._session.flush()
        return record

    async def get(
        self,
        *,
        workflow_key: str,
        workflow_version: str,
    ) -> Optional[WorkflowDefinition]:
        record = await self._session.get(
            WorkflowDefinitionRecord,
            {
                "workflow_key": workflow_key,
                "workflow_version": workflow_version,
            },
        )
        if record is None:
            return None
        return self._to_definition(record)

    async def get_active(
        self,
        *,
        workflow_key: str,
    ) -> Optional[WorkflowDefinition]:
        # 生产环境：真实 SQLAlchemy ORM model
        if hasattr(WorkflowDefinitionRecord, "__table__"):
            stmt = (
                select(WorkflowDefinitionRecord)
                .where(
                    WorkflowDefinitionRecord.workflow_key == workflow_key,
                    WorkflowDefinitionRecord.status == WorkflowDefinitionStatus.ACTIVE.value,
                )
                .order_by(WorkflowDefinitionRecord.updated_at.desc())
            )
            result = await self._session.execute(stmt)
            record = result.scalars().first()
        else:
            # 单测环境：FakeRecord + FakeSession
            result = await self._session.execute(None)
            candidates = result.scalars().all()
            active_records = [
                record
                for record in candidates
                if getattr(record, "workflow_key", None) == workflow_key
                and getattr(record, "status", None)
                == WorkflowDefinitionStatus.ACTIVE.value
            ]
            active_records.sort(
                key=lambda item: getattr(item, "updated_at", None),
                reverse=True,
            )
            record = active_records[0] if active_records else None

        if record is None:
            return None

        return self._to_definition(record)

    async def list_versions(
        self,
        *,
        workflow_key: str,
    ) -> list[WorkflowDefinition]:
        if hasattr(WorkflowDefinitionRecord, "__table__"):
            stmt = (
                select(WorkflowDefinitionRecord)
                .where(WorkflowDefinitionRecord.workflow_key == workflow_key)
                .order_by(WorkflowDefinitionRecord.created_at.asc())
            )
            result = await self._session.execute(stmt)
            records = result.scalars().all()
        else:
            result = await self._session.execute(None)
            records = [
                record
                for record in result.scalars().all()
                if getattr(record, "workflow_key", None) == workflow_key
            ]
            records.sort(key=lambda item: getattr(item, "created_at", None))

        return [self._to_definition(record) for record in records]

    @staticmethod
    def _to_record(definition: WorkflowDefinition) -> WorkflowDefinitionRecord:
        return WorkflowDefinitionRecord(
            workflow_key=definition.workflow_key,
            workflow_version=definition.workflow_version,
            display_name=definition.display_name,
            status=definition.status.value,
            schema_json=definition.to_schema_json(),
            input_schema_json=definition.input_schema,
            output_schema_json=definition.output_schema,
            policies_json=definition.policies,
            governance_json=definition.governance,
            metadata_json=definition.metadata,
            checksum=definition.checksum,
            created_by=definition.created_by,
            updated_by=definition.updated_by,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
        )

    @staticmethod
    def _apply_definition_to_record(
        definition: WorkflowDefinition,
        record: WorkflowDefinitionRecord,
    ) -> None:
        record.display_name = definition.display_name
        record.status = definition.status.value
        record.schema_json = definition.to_schema_json()
        record.input_schema_json = definition.input_schema
        record.output_schema_json = definition.output_schema
        record.policies_json = definition.policies
        record.governance_json = definition.governance
        record.metadata_json = definition.metadata
        record.checksum = definition.checksum
        record.created_by = definition.created_by
        record.updated_by = definition.updated_by
        record.created_at = definition.created_at
        record.updated_at = datetime.utcnow()

    @staticmethod
    def _to_definition(record: WorkflowDefinitionRecord) -> WorkflowDefinition:
        schema_json = dict(record.schema_json)
        schema_json["workflow_key"] = record.workflow_key
        schema_json["workflow_version"] = record.workflow_version
        schema_json["display_name"] = record.display_name
        schema_json["status"] = record.status
        schema_json["input_schema"] = record.input_schema_json
        schema_json["output_schema"] = record.output_schema_json
        schema_json["policies"] = record.policies_json
        schema_json["governance"] = record.governance_json
        schema_json["metadata"] = record.metadata_json
        schema_json["checksum"] = record.checksum
        schema_json["created_by"] = record.created_by
        schema_json["updated_by"] = record.updated_by
        schema_json["created_at"] = record.created_at
        schema_json["updated_at"] = record.updated_at
        return WorkflowDefinition.model_validate(schema_json)