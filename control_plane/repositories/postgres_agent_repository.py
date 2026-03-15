from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, delete

from persistence.db import Database
from persistence.models import AgentRecord


class PostgresAgentRepository:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, agent: dict[str, Any]) -> dict[str, Any]:
        """
        约定 agent 结构:
        {
            "id": "agent-001",
            "name": "demo-agent",
            "version": "1.0.0",
            "status": "active",
            "tenant_id": "t1",
            "capabilities": {...},
            "metadata": {...},
            "heartbeat_at": datetime | None
        }
        """
        async with self._db.session() as session:
            existing = await session.get(AgentRecord, agent["id"])
            if existing:
                existing.name = agent["name"]
                existing.version = agent["version"]
                existing.status = agent["status"]
                existing.tenant_id = agent.get("tenant_id")
                existing.capabilities = agent.get("capabilities", {})
                existing.metadata_json = agent.get("metadata", {})
                existing.heartbeat_at = agent.get("heartbeat_at")
                row = existing
            else:
                row = AgentRecord(
                    id=agent["id"],
                    name=agent["name"],
                    version=agent["version"],
                    status=agent["status"],
                    tenant_id=agent.get("tenant_id"),
                    capabilities=agent.get("capabilities", {}),
                    metadata_json=agent.get("metadata", {}),
                    heartbeat_at=agent.get("heartbeat_at"),
                )
                session.add(row)

            await session.flush()
            return self._to_dict(row)

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        async with self._db.session() as session:
            row = await session.get(AgentRecord, agent_id)
            return self._to_dict(row) if row else None

    async def list(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            stmt = select(AgentRecord).order_by(AgentRecord.created_at.desc())
            if tenant_id:
                stmt = stmt.where(AgentRecord.tenant_id == tenant_id)

            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._to_dict(r) for r in rows]

    async def update_status(self, agent_id: str, status: str) -> bool:
        async with self._db.session() as session:
            row = await session.get(AgentRecord, agent_id)
            if not row:
                return False
            row.status = status
            await session.flush()
            return True

    async def touch_heartbeat(self, agent_id: str, at: datetime | None = None) -> bool:
        async with self._db.session() as session:
            row = await session.get(AgentRecord, agent_id)
            if not row:
                return False
            row.heartbeat_at = at or datetime.now(timezone.utc)
            await session.flush()
            return True

    async def delete(self, agent_id: str) -> bool:
        async with self._db.session() as session:
            stmt = delete(AgentRecord).where(AgentRecord.id == agent_id)
            result = await session.execute(stmt)
            return result.rowcount > 0

    @staticmethod
    def _to_dict(row: AgentRecord) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "version": row.version,
            "status": row.status,
            "tenant_id": row.tenant_id,
            "capabilities": row.capabilities,
            "metadata": row.metadata_json,
            "heartbeat_at": row.heartbeat_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }