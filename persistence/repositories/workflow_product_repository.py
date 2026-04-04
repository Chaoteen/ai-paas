from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import WorkflowProductRecord
from runtime.workflows.product_models import (
    WorkflowProduct,
    WorkflowProductExecutionBinding,
)


class WorkflowProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(record: WorkflowProductRecord) -> WorkflowProduct:
        return WorkflowProduct(
            product_key=record.product_key,
            product_version=record.product_version,
            display_name=record.display_name,
            status=record.status,
            public_api_schema_json=record.public_api_schema_json or {},
            ui_schema_json=record.ui_schema_json or {},
            execution_binding=WorkflowProductExecutionBinding(
                workflow_key=record.bound_workflow_key,
                workflow_version=record.bound_workflow_version,
                default_input_json=record.default_input_json or {},
                default_context_json=record.default_context_json or {},
                input_mapping_json=record.input_mapping_json or {},
            ),
            governance_json=record.governance_json or {},
            metadata_json=record.metadata_json or {},
            visibility=record.visibility,
            created_by=record.created_by,
            updated_by=record.updated_by,
        )

    async def upsert(self, product: WorkflowProduct) -> WorkflowProduct:
        stmt = select(WorkflowProductRecord).where(
            WorkflowProductRecord.product_key == product.product_key,
            WorkflowProductRecord.product_version == product.product_version,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        if existing is None:
            record = WorkflowProductRecord(
                product_key=product.product_key,
                product_version=product.product_version,
                display_name=product.display_name,
                status=product.status,
                public_api_schema_json=product.public_api_schema_json,
                ui_schema_json=product.ui_schema_json,
                bound_workflow_key=product.execution_binding.workflow_key,
                bound_workflow_version=product.execution_binding.workflow_version,
                default_input_json=product.execution_binding.default_input_json,
                default_context_json=product.execution_binding.default_context_json,
                input_mapping_json=product.execution_binding.input_mapping_json,
                governance_json=product.governance_json,
                metadata_json=product.metadata_json,
                visibility=product.visibility,
                created_by=product.created_by,
                updated_by=product.updated_by,
            )
            self._session.add(record)
            await self._session.flush()
            return self._to_domain(record)

        existing.display_name = product.display_name
        existing.status = product.status
        existing.public_api_schema_json = product.public_api_schema_json
        existing.ui_schema_json = product.ui_schema_json
        existing.bound_workflow_key = product.execution_binding.workflow_key
        existing.bound_workflow_version = product.execution_binding.workflow_version
        existing.default_input_json = product.execution_binding.default_input_json
        existing.default_context_json = product.execution_binding.default_context_json
        existing.input_mapping_json = product.execution_binding.input_mapping_json
        existing.governance_json = product.governance_json
        existing.metadata_json = product.metadata_json
        existing.visibility = product.visibility
        existing.updated_by = product.updated_by

        await self._session.flush()
        return self._to_domain(existing)

    async def get(
        self,
        *,
        product_key: str,
        product_version: str,
    ) -> Optional[WorkflowProduct]:
        stmt = select(WorkflowProductRecord).where(
            WorkflowProductRecord.product_key == product_key,
            WorkflowProductRecord.product_version == product_version,
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(record) if record else None

    async def get_active(
        self,
        *,
        product_key: str,
    ) -> Optional[WorkflowProduct]:
        stmt = (
            select(WorkflowProductRecord)
            .where(
                WorkflowProductRecord.product_key == product_key,
                WorkflowProductRecord.status == "active",
            )
            .order_by(WorkflowProductRecord.updated_at.desc())
        )
        record = (await self._session.execute(stmt)).scalars().first()
        return self._to_domain(record) if record else None