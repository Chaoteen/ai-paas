from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app
from runtime.preflight import (
    RuntimePreflightError,
    collect_runtime_preflight,
    require_runtime_ready,
)

pytestmark = pytest.mark.asyncio


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for runtime preflight integration test")
    return value


@pytest.fixture(autouse=True)
async def _runtime_env_guard():
    _require_env("POSTGRES_HOST")
    _require_env("POSTGRES_PORT")
    _require_env("POSTGRES_DB")
    _require_env("POSTGRES_USER")
    _require_env("POSTGRES_PASSWORD")
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379")
    yield


async def test_collect_runtime_preflight_returns_ready_report():
    report = await collect_runtime_preflight()

    assert isinstance(report, dict)
    assert report["ok"] is True

    components = report["components"]
    assert isinstance(components, dict)

    assert "postgres" in components
    assert "redis" in components
    assert "runtime_schema" in components

    assert components["postgres"]["ok"] is True
    assert components["redis"]["ok"] is True
    assert components["runtime_schema"]["ok"] is True


async def test_require_runtime_ready_passes_when_dependencies_are_healthy():
    report = await require_runtime_ready()

    assert report["ok"] is True
    assert report["components"]["postgres"]["ok"] is True
    assert report["components"]["redis"]["ok"] is True
    assert report["components"]["runtime_schema"]["ok"] is True


async def test_collect_runtime_preflight_marks_report_unhealthy_when_redis_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1")

    report = await collect_runtime_preflight()

    assert report["ok"] is False
    assert report["components"]["postgres"]["ok"] is True
    assert report["components"]["redis"]["ok"] is False
    assert report["components"]["runtime_schema"]["ok"] is True
    assert report["components"]["redis"]["error"]


async def test_require_runtime_ready_raises_when_redis_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1")

    with pytest.raises(RuntimePreflightError) as exc_info:
        await require_runtime_ready()

    message = str(exc_info.value).lower()
    assert "redis" in message


async def test_health_api_exposes_runtime_preflight_details():
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, dict)
    assert "ok" in body
    assert "components" in body

    assert "postgres" in body["components"]
    assert "redis" in body["components"]
    assert "runtime_schema" in body["components"]


async def test_health_api_returns_unhealthy_when_redis_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1")

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 503

    body = response.json()
    assert body["ok"] is False
    assert body["components"]["postgres"]["ok"] is True
    assert body["components"]["redis"]["ok"] is False
    assert "error" in body["components"]["redis"]
    assert body["components"]["redis"]["error"]