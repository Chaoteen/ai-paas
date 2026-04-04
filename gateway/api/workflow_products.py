from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, status

from persistence.repositories.workflow_product_repository import WorkflowProductRepository
from runtime.queue.task_models import TaskEnvelope, WorkflowTaskPayload
from runtime.queue.task_store import get_postgres_session_factory
from runtime.queue.task_submission_service import (
    TaskSubmissionConflictError,
    TaskSubmissionService,
    TaskSubmissionServiceError,
)
from runtime.workflows.product_models import (
    CreateWorkflowProductRequest,
    SubmitWorkflowProductRequest,
    WorkflowProductResponse,
    WorkflowProductSubmitResponse,
)

router = APIRouter(tags=["workflow-products"])


def _merge_dicts(left: dict, right: dict) -> dict:
    result = deepcopy(left)
    result.update(deepcopy(right))
    return result


async def get_workflow_product_submission_service() -> TaskSubmissionService:
    session_factory = await get_postgres_session_factory()
    return TaskSubmissionService(session_factory=session_factory)


@router.post(
    "/workflow/products",
    response_model=WorkflowProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_workflow_product(
    request: CreateWorkflowProductRequest,
) -> WorkflowProductResponse:
    session_factory = await get_postgres_session_factory()
    async with session_factory() as session:
        repo = WorkflowProductRepository(session)
        product = await repo.upsert(request.product)
        await session.commit()
        return WorkflowProductResponse(product=product)


@router.post(
    "/workflow/products/submit",
    response_model=WorkflowProductSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_workflow_product(
    request: SubmitWorkflowProductRequest,
    submission_service: TaskSubmissionService = Depends(
        get_workflow_product_submission_service
    ),
) -> WorkflowProductSubmitResponse:
    session_factory = await get_postgres_session_factory()

    async with session_factory() as session:
        repo = WorkflowProductRepository(session)

        if request.product_version:
            product = await repo.get(
                product_key=request.product_key,
                product_version=request.product_version,
            )
        else:
            product = await repo.get_active(product_key=request.product_key)

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow product not found",
            )

        if product.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workflow product is not active",
            )

        bound_workflow_key = product.execution_binding.workflow_key
        bound_workflow_version = product.execution_binding.workflow_version

        merged_input = _merge_dicts(
            product.execution_binding.default_input_json,
            request.input_json,
        )
        merged_context = _merge_dicts(
            product.execution_binding.default_context_json,
            request.context_json,
        )
        merged_metadata = _merge_dicts(product.metadata_json, request.metadata_json)

        payload = WorkflowTaskPayload(
            workflow_key=bound_workflow_key,
            workflow_version=bound_workflow_version,
            input=merged_input,
            context=merged_context,
            metadata={
                **merged_metadata,
                "product_binding": {
                    "product_key": product.product_key,
                    "product_version": product.product_version,
                },
            },
            trigger_source=request.trigger_source,
        )

        task = TaskEnvelope.for_workflow(
            tenant_id=request.tenant_id,
            payload=payload,
            queue_name="workflow_tasks",
            correlation_id=request.correlation_id,
            idempotency_key=request.idempotency_key,
        )

        try:
            result = await submission_service.submit_task(
                task=task,
                stream_name="workflow_tasks",
            )
        except TaskSubmissionConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate workflow product submission: {exc}",
            ) from exc
        except TaskSubmissionServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to durably submit workflow product task: {exc}",
            ) from exc

        return WorkflowProductSubmitResponse(
            task_id=result.task_id,
            task_type="workflow",
            queue_name=result.queue_name,
            stream_name=result.stream_name,
            status=result.status,
            durable=True,
            outbox_event_id=result.outbox_event_id,
            bound_workflow_key=bound_workflow_key,
            bound_workflow_version=bound_workflow_version,
        )