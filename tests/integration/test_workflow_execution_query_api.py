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
from persistence.db import Database
from persistence.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from persistence.settings import PostgresSettings
from runtime.queue.postgres_task_store import PostgresTaskStore
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import get_postgres_session_factory, reset_task_store
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
        pytest.skip(f"{name} is required for workflow execution query integration test")
    return value


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379").strip()


async def _clear_runtime_redis_streams() -> None:
    queue = RedisStreamQueueClient(redis_url=_redis_url())
    redis_client = await queue._get_redis()  # noqa: SLF001

    streams = ["agent_tasks", "generation_tasks", "workflow_tasks"]
    groups = [
        ("agent_tasks", "agent_workers"),
        ("generation_tasks", "generation_workers"),
        ("workflow_tasks", "workflow_workers"),
    ]

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
    db = Database(PostgresSettings())
    async with db.session_factory() as session:
        await session.execute(text("DELETE FROM workflow_execution_events"))
        await session.execute(text("DELETE FROM workflow_step_executions"))
        await session.execute(text("DELETE FROM workflow_executions"))
        await session.execute(text("DELETE FROM workflow_definitions"))
        await session.execute(text("DELETE FROM workflow_products"))
        await session.execute(text("DELETE FROM runtime_outbox_events"))
        await session.execute(text("DELETE FROM runtime_tasks"))
        await session.commit()
    await db.dispose()


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
    worker = _build_worker("workflow", queue, store, "workflow-execution-query-it")

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


async def _create_workflow_definition(
    *,
    workflow_key: str,
    workflow_version: str,
) -> None:
    session_factory = await get_postgres_session_factory()
    definition = WorkflowDefinition(
        workflow_key=workflow_key,
        workflow_version=workflow_version,
        display_name="Execution Query Flow",
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
                node_id="draft_product_plan",
                node_type=WorkflowNodeType.CAPABILITY,
                name="Draft Product Plan",
                capability_ref=CapabilityRef(
                    kind=CapabilityKind.AGENT,
                    key="product.plan.drafter",
                    version="1.0.0",
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
                target_node_id="draft_product_plan",
            ),
            WorkflowEdge(
                edge_id="e2",
                source_node_id="draft_product_plan",
                target_node_id="end",
            ),
        ],
        policies={"retry": "node-level"},
        governance={"tenant_scoped": True},
        metadata={"owner": "workflow-team"},
        checksum="workflow-execution-query-it",
        created_by="workflow-execution-query-it",
        updated_by="workflow-execution-query-it",
    )

    async with session_factory() as session:
        repo = WorkflowDefinitionRepository(session)
        await repo.create(definition)
        await session.commit()


async def _create_workflow_product(
    *,
    product_key: str,
    product_version: str,
    workflow_key: str,
    workflow_version: str,
) -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/workflow/products",
            json={
                "product": {
                    "product_key": product_key,
                    "product_version": product_version,
                    "display_name": "太阳能庭院灯产品规划助手",
                    "status": "active",
                    "public_api_schema_json": {
                        "type": "object",
                        "properties": {
                            "target_market": {"type": "string"},
                            "cost_target": {"type": "number"},
                            "style_direction": {"type": "string"},
                        },
                        "required": ["target_market", "cost_target"],
                    },
                    "ui_schema_json": {"form": []},
                    "execution_binding": {
                        "workflow_key": workflow_key,
                        "workflow_version": workflow_version,
                        "default_input_json": {},
                        "default_context_json": {"channel": "product_api"},
                        "input_mapping_json": {},
                    },
                    "governance_json": {},
                    "metadata_json": {"category": "manufacturing"},
                    "visibility": "tenant",
                }
            },
        )
        assert response.status_code == 201, response.text


async def _submit_workflow_product(
    *,
    product_key: str,
    target_market: str,
    cost_target: float,
    style_direction: str,
) -> dict:
    transport = ASGITransport(app=app)
    unique = uuid.uuid4().hex

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/workflow/products/submit",
            json={
                "tenant_id": "dev",
                "product_key": product_key,
                "input_json": {
                    "target_market": target_market,
                    "cost_target": cost_target,
                    "style_direction": style_direction,
                },
                "context_json": {"operator": "pm_assistant"},
                "metadata_json": {"request_channel": "web"},
                "trigger_source": "workflow_product_api",
                "idempotency_key": f"workflow-query-{unique}",
                "correlation_id": f"workflow-query-{unique}",
            },
        )
        assert response.status_code == 202, response.text
        return response.json()


@pytest_asyncio.fixture(autouse=True)
async def _workflow_execution_query_env_guard():
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


async def test_workflow_execution_query_api_mainline() -> None:
    workflow_key = "solar_lamp_execution_query_flow"
    workflow_version = "1.0.0"
    product_key = "solar_lamp_execution_query_product"
    product_version = "1.0.0"

    await _create_workflow_definition(
        workflow_key=workflow_key,
        workflow_version=workflow_version,
    )
    await _create_workflow_product(
        product_key=product_key,
        product_version=product_version,
        workflow_key=workflow_key,
        workflow_version=workflow_version,
    )

    submit_body = await _submit_workflow_product(
        product_key=product_key,
        target_market="EU garden retail",
        cost_target=12.5,
        style_direction="warm ambient minimalism",
    )
    task_id = submit_body["task_id"]

    await _run_relay_once()
    await _run_workflow_worker_until_idle()

    task_body = await _poll_task(task_id)
    assert task_body["task_id"] == task_id
    assert task_body["status"] == "succeeded"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        by_task_resp = await client.get(f"/api/v1/workflow/executions/by-task/{task_id}")
        assert by_task_resp.status_code == 200, by_task_resp.text
        by_task_body = by_task_resp.json()

        workflow_execution_id = by_task_body["workflow_execution_id"]
        assert by_task_body["task_id"] == task_id
        assert by_task_body["workflow_key"] == workflow_key
        assert by_task_body["workflow_version"] == workflow_version
        assert by_task_body["status"] == "succeeded"

        detail_resp = await client.get(
            f"/api/v1/workflow/executions/{workflow_execution_id}/detail"
        )
        assert detail_resp.status_code == 200, detail_resp.text
        detail_body = detail_resp.json()

        assert detail_body["execution"]["workflow_execution_id"] == workflow_execution_id
        assert detail_body["execution"]["task_id"] == task_id
        assert detail_body["summary"]["execution_status"] == "succeeded"
        assert detail_body["summary"]["step_count"] == 1
        assert detail_body["summary"]["event_count"] >= 4

        execution_resp = await client.get(
            f"/api/v1/workflow/executions/{workflow_execution_id}"
        )
        assert execution_resp.status_code == 200, execution_resp.text
        execution_body = execution_resp.json()
        assert execution_body["workflow_execution_id"] == workflow_execution_id
        assert execution_body["status"] == "succeeded"

        steps_resp = await client.get(
            f"/api/v1/workflow/executions/{workflow_execution_id}/steps"
        )
        assert steps_resp.status_code == 200, steps_resp.text
        steps_body = steps_resp.json()
        assert steps_body["total"] == 1
        assert steps_body["items"][0]["node_id"] == "draft_product_plan"
        assert steps_body["items"][0]["status"] == "succeeded"

        events_resp = await client.get(
            f"/api/v1/workflow/executions/{workflow_execution_id}/events"
        )
        assert events_resp.status_code == 200, events_resp.text
        events_body = events_resp.json()
        assert events_body["total"] >= 4

        event_types = [item["event_type"] for item in events_body["items"]]
        assert "execution.created" in event_types
        assert "execution.running" in event_types
        assert "step.created" in event_types
        assert "step.running" in event_types
        assert "step.succeeded" in event_types
        assert "execution.succeeded" in event_types

        timeline_resp = await client.get(
            f"/api/v1/workflow/executions/{workflow_execution_id}/timeline"
        )
        assert timeline_resp.status_code == 200, timeline_resp.text
        timeline_body = timeline_resp.json()
        assert timeline_body["workflow_execution_id"] == workflow_execution_id
        assert timeline_body["total"] == len(timeline_body["items"])
        assert timeline_body["items"][0]["event_type"] == "execution.created"
        assert timeline_body["items"][-1]["event_type"] == "execution.succeeded"

        list_resp = await client.get("/api/v1/workflow/executions", params={"tenant_id": "dev"})
        assert list_resp.status_code == 200, list_resp.text
        list_body = list_resp.json()
        assert list_body["total"] >= 1
        assert any(
            item["workflow_execution_id"] == workflow_execution_id
            for item in list_body["items"]
        )