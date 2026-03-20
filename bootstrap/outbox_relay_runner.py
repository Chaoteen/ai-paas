from __future__ import annotations

import asyncio
import os

from sqlalchemy.exc import ProgrammingError

from runtime.queue.outbox_relay import OutboxRelay
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import get_postgres_session_factory


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def _get_redis_url() -> str:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        return redis_url
    return "redis://localhost:6379"


async def build_outbox_relay() -> OutboxRelay:
    session_factory = await get_postgres_session_factory()
    queue_client = RedisStreamQueueClient(redis_url=_get_redis_url())

    return OutboxRelay(
        session_factory=session_factory,
        queue_client=queue_client,
        retry_backoff_seconds=_int_env("OUTBOX_RETRY_BACKOFF_SECONDS", 5),
    )


async def run_relay_forever() -> None:
    relay = await build_outbox_relay()

    batch_limit = _int_env("OUTBOX_BATCH_LIMIT", 100)
    sleep_seconds = float(os.getenv("OUTBOX_RELAY_SLEEP_SECONDS", "1.0"))

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