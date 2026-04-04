from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from bootstrap.outbox_relay_runner import build_outbox_relay
from bootstrap.runtime_worker_runner import _build_worker
from gateway.main import app
from persistence.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from persistence.repositories.workflow_execution_event_repository import (
    WorkflowExecutionEventRepository,
)
from persistence.repositories.workflow_execution_repository import (
    WorkflowExecutionRepository,
)
from persistence.repositories.workflow_step_execution_repository import (
    WorkflowStepExecutionRepository,
)
from runtime.queue.postgres_task_store import PostgresTaskStore
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import (
    get_postgres_session_factory,
    reset_task_store,
)
from runtime.workflows.models import (
    CapabilityKind,
    CapabilityRef,
    WorkflowDefinition,
    WorkflowDefinitionStatus,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
)

pytestmark = pytest.mark.asyncio


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for workflow runtime failure integration test")
    return value


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379").strip()


async def _clear_runtime_redis_streams() -> None:
    queue = RedisStreamQueueClient(redis_url=_redis_url())
    redis_client = await queue._get_redis()  # noqa: SLF001

    streams = ["workflow_tasks"]
    groups = [("workflow_tasks", "workflow_workers")]

    try:
        for stream_name, group_name in groups:
            try:
                await redis_client.xgroup_destroy(stream_name, group_name)
            except Exception:
                pass

        for stream_name in streams:
            try:
                await redis_client.delete(stream_name)
            except Exception:
                pass
    finally:
        try:
            await redis_client.aclose()
        except Exception:
            pass


async def _clear_runtime_tables() -> None:
    from persistence.db import Database
    from persistence.settings import PostgresSettings

    db = Database(PostgresSettings())
    async with db.session_factory() as session:  # noqa: SLF001 phase19去掉了_session前面的_
        await session.execute(text("DELETE FROM workflow_execution_events"))
        await session.execute(text("DELETE FROM workflow_step_executions"))
        await session.execute(text("DELETE FROM workflow_executions"))
        await session.execute(text("DELETE FROM workflow_definitions"))
        await session.execute(text("DELETE FROM runtime_outbox_events"))
        await session.execute(text("DELETE FROM runtime_tasks"))
        await session.commit()
    await db.engine.dispose()


async def _run_relay_once() -> None:
    relay = await build_outbox_relay()
    await relay.run_once(limit=100)

    queue_client = getattr(relay, "queue_client", None) or getattr(relay, "_queue_client", None)
    if queue_client is not None:
        redis_client = getattr(queue_client, "_redis", None)
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                pass


async def _run_workflow_worker_until_idle() -> None:
    queue = RedisStreamQueueClient(redis_url=_redis_url())
    session_factory = await get_postgres_session_factory()
    store = PostgresTaskStore(session_factory=session_factory)
    worker = _build_worker("workflow", queue, store, "workflow-worker-failure-it")

    try:
        for _ in range(10):
            processed = await worker.run_once(count=10, block_ms=100)
            if processed == 0:
                break
    finally:
        redis_client = getattr(queue, "_redis", None)
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                pass


async def _poll_task(task_id: str, *, timeout_seconds: float = 20.0) -> dict:
    transport = ASGITransport(app=app)
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200, response.text
            body = response.json()
            if body["status"] in {"succeeded", "failed"}:
                return body
            await asyncio.sleep(0.25)

    raise AssertionError(f"Task did not finish within {timeout_seconds} seconds: {task_id}")


async def _create_workflow_definition(
    *,
    workflow_key: str,
    workflow_version: str,
) -> None:
    session_factory = await get_postgres_session_factory()
    definition = WorkflowDefinition(
        workflow_key=workflow_key,
        workflow_version=workflow_version,
        display_name="Pricing Quote Failure Flow",
        status=WorkflowDefinitionStatus.ACTIVE,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        nodes=[
            WorkflowNode(
                node_id="start",
                node_type=WorkflowNodeType.START,
                name="Start",
            ),
            WorkflowNode(
                node_id="draft_quote",
                node_type=WorkflowNodeType.CAPABILITY,
                name="Draft Quote",
                capability_ref=CapabilityRef(
                    kind=CapabilityKind.AGENT,
                    key="sales.quote.drafter",
                    version="1.2.0",
                ),
            ),
            WorkflowNode(
                node_id="end",
                node_type=WorkflowNodeType.END,
                name="End",
            ),
        ],
        edges=[
            WorkflowEdge(
                edge_id="e1",
                source_node_id="start",
                target_node_id="draft_quote",
            ),
            WorkflowEdge(
                edge_id="e2",
                source_node_id="draft_quote",
                target_node_id="end",
            ),
        ],
        policies={"retry": "node-level"},
        governance={"tenant_scoped": True},
        metadata={"owner": "workflow-team"},
        checksum="it-workflow-failure-checksum",
        created_by="workflow-failure-it",
        updated_by="workflow-failure-it",
    )

    async with session_factory() as session:
        repo = WorkflowDefinitionRepository(session)
        await repo.create(definition)
        await session.commit()


async def _get_execution_by_task(task_id: str):
    session_factory = await get_postgres_session_factory()
    async with session_factory() as session:
        repo = WorkflowExecutionRepository(session)
        return await repo.get_by_task_id(task_id)


async def _get_step_items(workflow_execution_id: str):
    session_factory = await get_postgres_session_factory()
    async with session_factory() as session:
        repo = WorkflowStepExecutionRepository(session)
        return await repo.list_by_execution(workflow_execution_id=workflow_execution_id)


async def _get_event_items(workflow_execution_id: str):
    session_factory = await get_postgres_session_factory()
    async with session_factory() as session:
        repo = WorkflowExecutionEventRepository(session)
        return await repo.list_by_execution(workflow_execution_id=workflow_execution_id)


@pytest_asyncio.fixture(autouse=True)
async def _workflow_runtime_env_guard():
    os.environ["TASK_STORE_BACKEND"] = "postgres"
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379"

    _require_env("POSTGRES_HOST")
    _require_env("POSTGRES_PORT")
    _require_env("POSTGRES_DB")
    _require_env("POSTGRES_USER")
    _require_env("POSTGRES_PASSWORD")

    await reset_task_store()
    await _clear_runtime_tables()
    await _clear_runtime_redis_streams()
    yield
    await reset_task_store()


async def test_workflow_submit_relay_worker_failure_e2e():
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379"

    workflow_key = f"pricing.quote.failure.flow.{uuid.uuid4().hex[:8]}"
    workflow_version = "1.0.0"
    await _create_workflow_definition(
        workflow_key=workflow_key,
        workflow_version=workflow_version,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        submit_response = await client.post(
            "/api/v1/workflow/submit",
            json={
                "tenant_id": "dev",
                "workflow_key": workflow_key,
                "workflow_version": workflow_version,
                "input": {
                    "customer_name": "Acme",
                    "force_fail_node_id": "draft_quote",
                },
                "context": {
                    "channel": "api",
                },
                "metadata": {
                    "source": "workflow-failure-mainline-it",
                },
                "trigger_source": "api",
            },
        )

        assert submit_response.status_code == 202, submit_response.text
        task_id = submit_response.json()["task_id"]

    await _run_relay_once()
    await _run_workflow_worker_until_idle()

    task_body = await _poll_task(task_id)
    assert task_body["task_id"] == task_id
    assert task_body["status"] == "failed"
    assert task_body["error"] is not None

    execution = await _get_execution_by_task(task_id)
    assert execution is not None
    assert execution.status.value == "failed"
    assert execution.active_node_ids == []
    assert execution.error_text is not None
    assert execution.output_json is not None
    assert execution.output_json["final_status"] == "failed"

    step_items = await _get_step_items(execution.workflow_execution_id)
    assert len(step_items) == 1
    assert step_items[0].node_id == "draft_quote"
    assert step_items[0].status.value == "failed"
    assert step_items[0].error_text is not None

    event_items = await _get_event_items(execution.workflow_execution_id)
    event_types = [item.event_type.value for item in event_items]
    assert event_types == [
        "execution.created",
        "execution.running",
        "step.created",
        "step.running",
        "step.failed",
        "execution.failed",
    ]