from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import text


class PostgresDataEventRepository:
    """
    方案A正式版：
    使用 data_events_v2
    主键 id 为 UUID
    """

    def __init__(self, db):
        self.db = db

    def _parse_occurred_at(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        raise TypeError(f"Unsupported occurred_at type: {type(value)}")

    async def save(self, event: Dict[str, Any]) -> Dict[str, Any]:
        sql = text(
            """
            INSERT INTO data_events_v2 (
                id,
                event_type,
                stream,
                source,
                tenant_id,
                correlation_id,
                task_id,
                workflow_id,
                payload,
                occurred_at,
                schema_version,
                retry_count,
                headers
            )
            VALUES (
                CAST(:id AS UUID),
                :event_type,
                :stream,
                :source,
                :tenant_id,
                :correlation_id,
                :task_id,
                :workflow_id,
                CAST(:payload AS JSONB),
                :occurred_at,
                :schema_version,
                :retry_count,
                CAST(:headers AS JSONB)
            )
            """
        )

        params = {
            "id": event["id"],
            "event_type": event["event_type"],
            "stream": event["stream"],
            "source": event["source"],
            "tenant_id": event.get("tenant_id"),
            "correlation_id": event.get("correlation_id"),
            "task_id": event.get("task_id"),
            "workflow_id": event.get("workflow_id"),
            "payload": json.dumps(event.get("payload", {}), ensure_ascii=False),
            "occurred_at": self._parse_occurred_at(event["occurred_at"]),
            "schema_version": event.get("schema_version", "1.0"),
            "retry_count": int(event.get("retry_count", 0)),
            "headers": json.dumps(event.get("headers", {}), ensure_ascii=False),
        }

        async with self.db.session() as session:
            await session.execute(sql, params)

        return event

    async def list_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if event_type:
            sql = text(
                """
                SELECT
                    id,
                    event_type,
                    stream,
                    source,
                    tenant_id,
                    correlation_id,
                    task_id,
                    workflow_id,
                    payload,
                    occurred_at,
                    created_at,
                    schema_version,
                    retry_count,
                    headers
                FROM data_events_v2
                WHERE event_type = :event_type
                ORDER BY occurred_at DESC
                LIMIT :limit
                """
            )
            params = {
                "event_type": event_type,
                "limit": limit,
            }
        else:
            sql = text(
                """
                SELECT
                    id,
                    event_type,
                    stream,
                    source,
                    tenant_id,
                    correlation_id,
                    task_id,
                    workflow_id,
                    payload,
                    occurred_at,
                    created_at,
                    schema_version,
                    retry_count,
                    headers
                FROM data_events_v2
                ORDER BY occurred_at DESC
                LIMIT :limit
                """
            )
            params = {"limit": limit}

        async with self.db.session() as session:
            result = await session.execute(sql, params)
            rows = result.mappings().all()

        items: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("occurred_at") is not None:
                item["occurred_at"] = item["occurred_at"].isoformat()
            if item.get("created_at") is not None:
                item["created_at"] = item["created_at"].isoformat()
            item["payload"] = item.get("payload") or {}
            item["headers"] = item.get("headers") or {}
            items.append(item)

        return items