from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class PersistenceConfigurationError(RuntimeError):
    """Raised when persistence/database configuration is invalid."""


_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _build_database_url_from_postgres_parts() -> Optional[str]:
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")

    if not all([host, db, user, password]):
        return None

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def _resolve_database_url() -> str:
    """
    Formal single source of truth for async SQLAlchemy database URL resolution.

    Resolution order:
    1. DATABASE_URL
    2. POSTGRES_DSN
    3. POSTGRES_HOST / PORT / DB / USER / PASSWORD
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url.strip()

    postgres_dsn = os.getenv("POSTGRES_DSN")
    if postgres_dsn:
        return postgres_dsn.strip()

    database_url = _build_database_url_from_postgres_parts()
    if database_url:
        return database_url

    raise PersistenceConfigurationError(
        "DATABASE_URL or POSTGRES_DSN must be configured, "
        "or POSTGRES_HOST/POSTGRES_PORT/POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD must all be set"
    )


def get_async_engine() -> AsyncEngine:
    global _engine

    if _engine is not None:
        return _engine

    database_url = _resolve_database_url()
    _engine = create_async_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
    )
    return _engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory

    if _session_factory is not None:
        return _session_factory

    engine = get_async_engine()
    _session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return _session_factory


async def dispose_async_engine() -> None:
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    _session_factory = None


class Database:
    """
    Compatibility wrapper around the formal persistence runtime.

    Existing code that still expects Database(...).engine / session_factory / dispose()
    should resolve to the same shared engine/session-factory managed in this module.
    """

    def __init__(self, _settings: object | None = None) -> None:
        self.engine = get_async_engine()
        self.session_factory = get_async_session_factory()

    async def dispose(self) -> None:
        await dispose_async_engine()