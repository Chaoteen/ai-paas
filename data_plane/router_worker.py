from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data_plane.data_bus import DATA_EVENTS_STREAM, DataBus
from data_plane.redis_stream_bus import RedisStreamBus


def _parse_dt(value: Any) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


class RouterWorker:
    def __init__(
        self,
        *,
        agent_registry: Any,
        data_bus: DataBus,
        event_bus: RedisStreamBus,
        consumer_group: str = "router-workers",
        consumer_name: str = "router-1",
    ) -> None:
        self.agent_registry = agent_registry
        self.data_bus = data_bus
        self.event_bus = event_bus
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self._running = False

    async def start(self) -> None:
        self.event_bus.ensure_group(DATA_EVENTS_STREAM, self.consumer_group)
        self._running = True

        while self._running:
            messages = self.event_bus.consume(
                stream=DATA_EVENTS_STREAM,
                group_name=self.consumer_group,
                consumer_name=self.consumer_name,
                count=10,
                block_ms=1000,
            )

            if not messages:
                await asyncio.sleep(0.2)
                continue

            for msg in messages:
                try:
                    await self._handle_envelope(msg.envelope)
                    self.event_bus.ack(msg.stream, self.consumer_group, msg.message_id)
                except Exception as exc:
                    self.event_bus.dead_letter(
                        original_stream=msg.stream,
                        envelope=msg.envelope,
                        reason=str(exc),
                    )
                    self.event_bus.ack(msg.stream, self.consumer_group, msg.message_id)

    async def stop(self) -> None:
        self._running = False

    async def _handle_envelope(self, envelope) -> None:
        if envelope.event_type != "task.submitted":
            return

        task_id = envelope.task_id or envelope.payload.get("task_id")
        workflow_id = envelope.workflow_id or envelope.payload.get("workflow_id")
        tenant_id = envelope.tenant_id
        correlation_id = envelope.correlation_id
        required_capability = envelope.payload.get("required_capability")
        input_payload = envelope.payload.get("input")
        metadata = envelope.payload.get("metadata", {})

        if not task_id:
            await self.data_bus.router_failed(
                task_id="unknown-task",
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                error="TASK_ID_MISSING",
            )
            return

        if not required_capability:
            await self.data_bus.router_failed(
                task_id=task_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                error="REQUIRED_CAPABILITY_MISSING",
            )
            return

        agents = await self.agent_registry.list_agents(tenant_id=tenant_id)
        selected = self._select_agent(
            agents=agents,
            tenant_id=tenant_id,
            required_capability=required_capability,
        )

        if selected is None:
            await self.data_bus.router_failed(
                task_id=task_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                error="NO_ELIGIBLE_AGENT",
                extra={
                    "required_capability": required_capability,
                },
            )
            return

        await self.data_bus.router_success(
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            route_to=selected.get("id") or selected.get("name") or "unknown-agent",
            extra={
                "selected_agent_id": selected.get("id"),
                "selected_agent_name": selected.get("name"),
                "required_capability": required_capability,
                "input": input_payload,
                "metadata": metadata,
            },
        )

    def _select_agent(
        self,
        *,
        agents: List[Dict[str, Any]],
        tenant_id: Optional[str],
        required_capability: str,
    ) -> Optional[Dict[str, Any]]:
        eligible: List[Dict[str, Any]] = []

        for agent in agents:
            if tenant_id is not None and agent.get("tenant_id") != tenant_id:
                continue

            status = str(agent.get("status", "")).lower()
            if status not in {"healthy", "online", "ready", "active"}:
                continue

            capabilities = agent.get("capabilities") or {}
            if isinstance(capabilities, str):
                try:
                    import json
                    capabilities = json.loads(capabilities)
                except Exception:
                    capabilities = {}

            skills = []
            if isinstance(capabilities, dict):
                skills = capabilities.get("skills", []) or []

            if required_capability not in skills:
                continue

            eligible.append(agent)

        if not eligible:
            return None

        eligible.sort(
            key=lambda x: max(
                _parse_dt(x.get("heartbeat_at")),
                _parse_dt(x.get("last_heartbeat_at")),
                _parse_dt(x.get("updated_at")),
            ),
            reverse=True,
        )
        return eligible[0]