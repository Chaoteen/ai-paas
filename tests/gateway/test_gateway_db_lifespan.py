from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from gateway.main import app


def _has_db_env() -> bool:
    return bool(
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DSN")
        or (
            os.getenv("POSTGRES_HOST")
            and os.getenv("POSTGRES_DB")
            and os.getenv("POSTGRES_USER")
            and os.getenv("POSTGRES_PASSWORD")
        )
    )


@pytest.fixture(autouse=True)
def require_db_env() -> None:
    if not _has_db_env():
        pytest.skip(
            "DB env not configured. Set DATABASE_URL, POSTGRES_DSN, "
            "or POSTGRES_HOST/POSTGRES_PORT/POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD."
        )


def test_gateway_lifespan_allows_sequential_testclients() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200