from __future__ import annotations

import os
from typing import Any

import asyncpg
from redis.asyncio import Redis


class RuntimePreflightError(RuntimeError):
    """Raised when runtime dependencies are not ready for production traffic."""


def _postgres_config() -> dict[str, Any]:
    return {
        "host": os.getenv("POSTGRES_HOST", "").strip(),
        "port": int(os.getenv("POSTGRES_PORT", "5432").strip()),
        "database": os.getenv("POSTGRES_DB", "").strip(),
        "user": os.getenv("POSTGRES_USER", "").strip(),
        "password": os.getenv("POSTGRES_PASSWORD", "").strip(),
    }


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379").strip()


async def _check_postgres() -> dict[str, Any]:
    cfg = _postgres_config()

    missing = [k for k, v in cfg.items() if not v]
    if missing:
        return {
            "ok": False,
            "error": f"missing postgres settings: {', '.join(missing)}",
        }

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(**cfg)
        value = await conn.fetchval("SELECT 1")
        return {
            "ok": value == 1,
            "details": {
                "host": cfg["host"],
                "port": cfg["port"],
                "database": cfg["database"],
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }
    finally:
        if conn is not None:
            await conn.close()


async def _check_redis() -> dict[str, Any]:
    redis_url = _redis_url()
    client: Redis | None = None

    try:
        client = Redis.from_url(redis_url, decode_responses=True)
        pong = await client.ping()
        return {
            "ok": bool(pong),
            "details": {
                "url": redis_url,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }
    finally:
        if client is not None:
            await client.close()


async def _check_runtime_schema() -> dict[str, Any]:
    cfg = _postgres_config()

    missing = [k for k, v in cfg.items() if not v]
    if missing:
        return {
            "ok": False,
            "error": f"missing postgres settings: {', '.join(missing)}",
        }

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(**cfg)

        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('runtime_tasks', 'runtime_outbox_events')
            """
        )
        found = {row["table_name"] for row in rows}
        required = {"runtime_tasks", "runtime_outbox_events"}
        missing_tables = sorted(required - found)

        if missing_tables:
            return {
                "ok": False,
                "error": f"missing runtime tables: {', '.join(missing_tables)}",
            }

        status_constraint = await conn.fetchval(
            """
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t
              ON t.oid = c.conrelid
            WHERE t.relname = 'runtime_outbox_events'
              AND c.conname = 'chk_runtime_outbox_status'
            """
        )

        if not status_constraint:
            return {
                "ok": False,
                "error": "missing constraint: chk_runtime_outbox_status",
            }

        return {
            "ok": True,
            "details": {
                "tables": sorted(found),
                "constraint": "chk_runtime_outbox_status",
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }
    finally:
        if conn is not None:
            await conn.close()


async def collect_runtime_preflight() -> dict[str, Any]:
    postgres = await _check_postgres()
    redis = await _check_redis()
    runtime_schema = await _check_runtime_schema()

    components = {
        "postgres": postgres,
        "redis": redis,
        "runtime_schema": runtime_schema,
    }

    ok = all(component.get("ok", False) for component in components.values())

    return {
        "ok": ok,
        "components": components,
    }


async def require_runtime_ready() -> dict[str, Any]:
    report = await collect_runtime_preflight()
    if report["ok"]:
        return report

    failed = [
        name
        for name, result in report["components"].items()
        if not result.get("ok", False)
    ]
    raise RuntimePreflightError(
        f"runtime preflight failed: {', '.join(failed)}"
    )
