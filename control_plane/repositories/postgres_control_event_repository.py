from __future__ import annotations

from typing import Any

from sqlalchemy import select

from persistence.db import Database
from persistence.models import ControlEventRecord


class PostgresControlEventRepository:
    def __init__(self, db: Database):
        self._db = db

    async def append(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        约定 event 结构:
        {
            "id": "optional",
            "event_type": "agent.registered",
            "agent_id": "agent-001",
            "tenant_id": "t1",
            "payload": {...}
        }
        """
        async with self._db.session() as session:
            row = ControlEventRecord(
                id=event.get("id") or None,
                event_type=event["event_type"],
                agent_id=event.get("agent_id"),
                tenant_id=event.get("tenant_id"),
                payload=event.get("payload", {}),
            )
            session.add(row)
            await session.flush()
            return self._to_dict(row)

    async def list(
        self,
        event_type: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            stmt = select(ControlEventRecord).order_by(ControlEventRecord.occurred_at.desc()).limit(limit)

            if event_type:
                stmt = stmt.where(ControlEventRecord.event_type == event_type)
            if agent_id:
                stmt = stmt.where(ControlEventRecord.agent_id == agent_id)

            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_dict(r) for r in rows]

    @staticmethod
    def _to_dict(row: ControlEventRecord) -> dict[str, Any]:
        return {
            "id": row.id,
            "event_type": row.event_type,
            "agent_id": row.agent_id,
            "tenant_id": row.tenant_id,
            "payload": row.payload,
            "occurred_at": row.occurred_at,
        }