from __future__ import annotations

import os

import pytest

from persistence.db import get_async_engine, get_async_session_factory
from runtime.queue.task_store import (
    get_postgres_session_factory,
    reset_task_store,
    shutdown_task_store_runtime_state,
)


pytestmark = pytest.mark.asyncio


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


async def test_get_postgres_session_factory_uses_formal_persistence_entrypoint() -> None:
    task_store_factory = await get_postgres_session_factory()
    persistence_factory = get_async_session_factory()

    assert task_store_factory is persistence_factory


async def test_reset_task_store_does_not_break_shared_factory_cache() -> None:
    first_factory = await get_postgres_session_factory()
    await reset_task_store()
    second_factory = await get_postgres_session_factory()

    assert first_factory is second_factory


async def test_shutdown_task_store_runtime_state_disposes_shared_engine() -> None:
    first_engine = get_async_engine()
    first_factory = get_async_session_factory()

    await shutdown_task_store_runtime_state()

    second_engine = get_async_engine()
    second_factory = get_async_session_factory()

    assert first_engine is not second_engine
    assert first_factory is not second_factory