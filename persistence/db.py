from __future__ import annotations

import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator, Any
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class PersistenceConfigurationError(Exception):
    """Raised when persistence configuration is missing or invalid."""


def _resolve_database_url() -> str:
    """
    Resolve the async SQLAlchemy database URL.

    Priority:
    1. DATABASE_URL
    2. POSTGRES_DSN

    Expected format for async usage:
    postgresql+asyncpg://user:pass@host:port/dbname
    """
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DSN")
        or ""
    ).strip()

    if not database_url:
        raise PersistenceConfigurationError(
            "DATABASE_URL or POSTGRES_DSN must be configured"
        )

    if not database_url.startswith("postgresql+asyncpg://"):
        raise PersistenceConfigurationError(
            "Database URL must use async SQLAlchemy driver prefix "
            "'postgresql+asyncpg://'"
        )

    return database_url


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    database_url = _resolve_database_url()

    return create_async_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = get_async_engine()
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_async_engine() -> None:
    """
    Dispose cached async engine.

    Useful in tests or controlled shutdown paths.
    """
    try:
        engine = get_async_engine()
    except PersistenceConfigurationError:
        return

    await engine.dispose()
    get_async_engine.cache_clear()
    get_async_session_factory.cache_clear()


def _build_async_url_from_settings(settings: Any) -> str:
    """
    Build asyncpg SQLAlchemy URL from PostgresSettings-like object.

    Expected attributes:
    - host
    - port
    - database
    - user
    - password

    Optional attributes:
    - async_database_url
    - database_url
    """
    for attr in ("async_database_url", "database_url"):
        value = getattr(settings, attr, None)
        if isinstance(value, str) and value.strip():
            url = value.strip()
            if not url.startswith("postgresql+asyncpg://"):
                raise PersistenceConfigurationError(
                    f"{attr} must use 'postgresql+asyncpg://' prefix"
                )
            return url

    host = getattr(settings, "host", None)
    port = getattr(settings, "port", None)
    database = getattr(settings, "database", None)
    user = getattr(settings, "user", None)
    password = getattr(settings, "password", None)

    missing = [
        name for name, value in [
            ("host", host),
            ("port", port),
            ("database", database),
            ("user", user),
            ("password", password),
        ]
        if value in (None, "")
    ]
    if missing:
        raise PersistenceConfigurationError(
            "Missing database settings fields: " + ", ".join(missing)
        )

    return (
        "postgresql+asyncpg://"
        f"{quote_plus(str(user))}:{quote_plus(str(password))}"
        f"@{host}:{port}/{database}"
    )


class Database:
    """
    Compatibility wrapper retained for repositories/tests that still use:

        database = Database(settings)
        async with database.engine.begin() as conn: ...
        async with database.session() as session: ...
        await database.dispose()

    This is a thin async SQLAlchemy wrapper and should be treated as a
    compatibility layer during formal-release governance.
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self.database_url = _build_async_url_from_settings(settings)
        self.engine: AsyncEngine = create_async_engine(
            self.database_url,
            echo=bool(getattr(settings, "echo", False)),
            future=True,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def dispose(self) -> None:
        await self.engine.dispose()
