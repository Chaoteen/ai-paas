from __future__ import annotations

import asyncio
import os

from sqlalchemy.exc import ProgrammingError

from runtime.preflight import require_runtime_ready
from runtime.queue.outbox_relay import OutboxRelay
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import get_postgres_session_factory


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    value = int(raw.strip())
    if value <= 0:
        raise ValueError(f"{name} must be > 0")

    return value


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    value = float(raw.strip())
    if value <= 0:
        raise ValueError(f"{name} must be > 0")

    return value


def _get_redis_url() -> str:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        raise ValueError("REDIS_URL is required")
    return redis_url


async def build_outbox_relay() -> OutboxRelay:
    session_factory = await get_postgres_session_factory()
    queue_client = RedisStreamQueueClient(redis_url=_get_redis_url())

    return OutboxRelay(
        session_factory=session_factory,
        queue_client=queue_client,
        retry_backoff_seconds=_positive_int_env("OUTBOX_RETRY_BACKOFF_SECONDS", 5),
        max_publish_attempts=_positive_int_env("OUTBOX_MAX_PUBLISH_ATTEMPTS", 10),
    )


async def run_relay_forever() -> None:
    await require_runtime_ready()

    relay = await build_outbox_relay()
    batch_limit = _positive_int_env("OUTBOX_BATCH_LIMIT", 100)
    sleep_seconds = _float_env("OUTBOX_RELAY_SLEEP_SECONDS", 1.0)

    while True:
        try:
            result = await relay.run_once(limit=batch_limit)
        except ProgrammingError as exc:
            message = str(exc)
            if "runtime_outbox_events" in message:
                raise RuntimeError(
                    "Outbox relay startup failed: table 'runtime_outbox_events' does not exist. "
                    "Run the runtime database migrations first."
                ) from exc
            raise

        if result.scanned == 0:
            await asyncio.sleep(sleep_seconds)


def main() -> None:
    asyncio.run(run_relay_forever())


if __name__ == "__main__":
    main()