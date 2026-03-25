from __future__ import annotations

import asyncio
import os
from typing import Literal

from runtime.preflight import require_runtime_ready
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import get_task_store
from runtime.workers.agent_worker import AgentWorker
from runtime.workers.generation_worker import GenerationWorker

WorkerKind = Literal["agent", "generation"]


def _get_redis_url() -> str:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        return redis_url
    return "redis://localhost:6379"


def _get_worker_kind() -> WorkerKind:
    kind = os.getenv("AI_PAAS_WORKER_KIND", "agent").strip().lower()
    if kind not in {"agent", "generation"}:
        raise RuntimeError(
            "AI_PAAS_WORKER_KIND must be 'agent' or 'generation'"
        )
    return kind  # type: ignore[return-value]


def _get_consumer_name(kind: WorkerKind) -> str:
    default_name = f"{kind}-worker-1"
    return os.getenv("AI_PAAS_WORKER_CONSUMER_NAME", default_name).strip()


def _build_worker(kind: WorkerKind, queue_client, store, consumer_name: str):
    if kind == "agent":
        return AgentWorker(
            queue=queue_client,
            store=store,
            consumer_name=consumer_name,
        )

    return GenerationWorker(
        queue=queue_client,
        store=store,
        consumer_name=consumer_name,
    )


async def run_worker_forever() -> None:
    await require_runtime_ready()

    kind = _get_worker_kind()
    consumer_name = _get_consumer_name(kind)
    queue_client = RedisStreamQueueClient(redis_url=_get_redis_url())
    store = await get_task_store()
    worker = _build_worker(kind, queue_client, store, consumer_name)

    block_ms = int(os.getenv("AI_PAAS_WORKER_BLOCK_MS", "1000"))
    count = int(os.getenv("AI_PAAS_WORKER_BATCH_COUNT", "1"))
    idle_sleep = float(os.getenv("AI_PAAS_WORKER_IDLE_SLEEP_SECONDS", "0.2"))

    while True:
        processed = await worker.run_once(count=count, block_ms=block_ms)
        if processed == 0:
            await asyncio.sleep(idle_sleep)


def main() -> None:
    asyncio.run(run_worker_forever())


if __name__ == "__main__":
    main()