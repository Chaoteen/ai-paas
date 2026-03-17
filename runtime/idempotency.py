from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    owner: str
    created_at: str = field(default_factory=utc_now_iso)
    last_seen_at: str = field(default_factory=utc_now_iso)
    hit_count: int = 1

    def touch(self) -> None:
        self.last_seen_at = utc_now_iso()
        self.hit_count += 1


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: Dict[str, IdempotencyRecord] = {}

    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        return self._records.get(key)

    async def acquire(self, *, key: str, owner: str) -> bool:
        record = self._records.get(key)
        if record is not None:
            record.touch()
            return False

        self._records[key] = IdempotencyRecord(key=key, owner=owner)
        return True

    async def release(self, key: str) -> None:
        self._records.pop(key, None)

    async def list_keys(self) -> list[str]:
        return sorted(self._records.keys())


def build_event_stage_key(*, task_id: str, stage: str) -> str:
    return f"task:{task_id}:stage:{stage}"


def build_event_type_key(*, task_id: str, event_type: str) -> str:
    return f"task:{task_id}:event:{event_type}"