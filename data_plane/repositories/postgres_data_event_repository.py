from __future__ import annotations

from typing import Any

from sqlalchemy import select

from persistence.db import Database
from persistence.models import DataEventRecord


class PostgresDataEventRepository:
    def __init__(self, db: Database):
        self._db = db

    async def append(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        约定 event 结构:
        {
            "id": "optional",
            "task_id": "task-001",
            "execution_id": "exec-001",
            "event_type": "task.created",
            "tenant_id": "t1",
            "payload": {...}
        }
        """
        async with self._db.session() as session:
            row = DataEventRecord(
                id=event.get("id") or None,
                task_id=event.get("task_id"),
                execution_id=event.get("execution_id"),
                event_type=event["event_type"],
                tenant_id=event.get("tenant_id"),
                payload=event.get("payload", {}),
            )
            session.add(row)
            await session.flush()
            return self._to_dict(row)

    async def list(
        self,
        event_type: str | None = None,
        task_id: str | None = None,
        execution_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            stmt = select(DataEventRecord).order_by(DataEventRecord.occurred_at.desc()).limit(limit)

            if event_type:
                stmt = stmt.where(DataEventRecord.event_type == event_type)
            if task_id:
                stmt = stmt.where(DataEventRecord.task_id == task_id)
            if execution_id:
                stmt = stmt.where(DataEventRecord.execution_id == execution_id)

            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_dict(r) for r in rows]

    @staticmethod
    def _to_dict(row: DataEventRecord) -> dict[str, Any]:
        return {
            "id": row.id,
            "task_id": row.task_id,
            "execution_id": row.execution_id,
            "event_type": row.event_type,
            "tenant_id": row.tenant_id,
            "payload": row.payload,
            "occurred_at": row.occurred_at,
        }