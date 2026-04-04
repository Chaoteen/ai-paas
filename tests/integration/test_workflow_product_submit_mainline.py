from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from gateway.main import app


pytestmark = pytest.mark.integration


def _require_postgres_env() -> None:
    required = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(f"Missing Postgres env vars: {', '.join(missing)}")


def _build_database_url() -> str:
    host = os.environ["POSTGRES_HOST"]
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


async def _cleanup_tables() -> None:
    engine = create_async_engine(_build_database_url(), future=True, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM runtime_outbox_events"))
            await conn.execute(text("DELETE FROM runtime_tasks"))
            await conn.execute(text("DELETE FROM workflow_products"))
    finally:
        await engine.dispose()


async def _verify_db_state(task_id: str) -> None:
    engine = create_async_engine(_build_database_url(), future=True, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            task_row = (
                await conn.execute(
                    text(
                        """
                        SELECT task_id, tenant_id, task_type, queue_name, status
                        FROM runtime_tasks
                        WHERE task_id = :task_id
                        """
                    ),
                    {"task_id": task_id},
                )
            ).mappings().first()

            outbox_row = (
                await conn.execute(
                    text(
                        """
                        SELECT
                            event_id,
                            aggregate_type,
                            aggregate_id,
                            tenant_id,
                            event_type,
                            queue_name,
                            stream_name,
                            status
                        FROM runtime_outbox_events
                        WHERE aggregate_id = :task_id
                        ORDER BY event_id DESC
                        LIMIT 1
                        """
                    ),
                    {"task_id": task_id},
                )
            ).mappings().first()

        assert task_row is not None
        assert task_row["task_id"] == task_id
        assert task_row["tenant_id"] == "dev"
        assert task_row["task_type"] == "workflow"
        assert task_row["queue_name"] == "workflow_tasks"
        assert task_row["status"] == "queued"

        assert outbox_row is not None
        assert outbox_row["aggregate_id"] == task_id
        assert outbox_row["tenant_id"] == "dev"
        assert outbox_row["queue_name"] == "workflow_tasks"
        assert outbox_row["stream_name"] == "workflow_tasks"
        assert outbox_row["status"] in ("pending", "queued", "published")
    finally:
        await engine.dispose()


def test_workflow_product_submit_mainline() -> None:
    _require_postgres_env()

    unique = uuid4().hex

    asyncio.run(_cleanup_tables())

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/workflow/products",
            json={
                "product": {
                    "product_key": "solar_lamp_product_plan",
                    "product_version": "1.0.0",
                    "display_name": "太阳能庭院灯产品规划助手",
                    "status": "active",
                    "public_api_schema_json": {
                        "type": "object",
                        "properties": {
                            "target_market": {"type": "string"},
                            "cost_target": {"type": "number"},
                        },
                        "required": ["target_market", "cost_target"],
                    },
                    "ui_schema_json": {"form": []},
                    "execution_binding": {
                        "workflow_key": "solar_lamp_internal_flow",
                        "workflow_version": "3.2.0",
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
        assert create_resp.status_code == 201, create_resp.text

        submit_resp = client.post(
            "/api/v1/workflow/products/submit",
            json={
                "tenant_id": "dev",
                "product_key": "solar_lamp_product_plan",
                "input_json": {
                    "target_market": "EU garden retail",
                    "cost_target": 12.5,
                },
                "context_json": {"operator": "pm_assistant"},
                "metadata_json": {"request_channel": "web"},
                "trigger_source": "workflow_product_api",
                "idempotency_key": f"order-integration-{unique}",
                "correlation_id": f"corr-integration-{unique}",
            },
        )
        assert submit_resp.status_code == 202, submit_resp.text

        body = submit_resp.json()
        task_id = body["task_id"]

        assert body["task_type"] == "workflow"
        assert body["queue_name"] == "workflow_tasks"
        assert body["stream_name"] == "workflow_tasks"
        assert body["status"] == "queued"
        assert body["bound_workflow_key"] == "solar_lamp_internal_flow"
        assert body["bound_workflow_version"] == "3.2.0"

    asyncio.run(_verify_db_state(task_id))