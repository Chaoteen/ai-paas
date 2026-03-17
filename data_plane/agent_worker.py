from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from data_plane.data_bus import DATA_EVENTS_STREAM, DataBus
from data_plane.redis_stream_bus import RedisStreamBus


class AgentWorker:
    """
    Phase 9 MVP:
    - 消费 router.success
    - 发布 task.executing
    - 模拟 Agent 执行
    - 发布 task.completed / task.failed
    """

    def __init__(
        self,
        *,
        agent_registry: Any,
        data_bus: DataBus,
        event_bus: RedisStreamBus,
        consumer_group: str = "agent-workers",
        consumer_name: str = "agent-1",
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
        if envelope.event_type != "router.success":
            return

        task_id = envelope.task_id or envelope.payload.get("task_id")
        workflow_id = envelope.workflow_id or envelope.payload.get("workflow_id")
        tenant_id = envelope.tenant_id
        correlation_id = envelope.correlation_id

        payload = envelope.payload or {}
        route_to = payload.get("route_to")
        extra = payload.get("extra", {}) or {}
        selected_agent_id = extra.get("selected_agent_id") or route_to
        selected_agent_name = extra.get("selected_agent_name")
        required_capability = extra.get("required_capability")
        input_payload = extra.get("input")
        metadata = extra.get("metadata", {})

        if not task_id:
            return

        await self.data_bus.task_executing(
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            route_to=route_to,
            extra={
                "selected_agent_id": selected_agent_id,
                "selected_agent_name": selected_agent_name,
            },
        )

        agent = await self._get_agent_by_id(
            tenant_id=tenant_id,
            agent_id=selected_agent_id,
        )

        if agent is None:
            await self.data_bus.task_failed(
                task_id=task_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                error="AGENT_NOT_FOUND",
                extra={
                    "selected_agent_id": selected_agent_id,
                    "route_to": route_to,
                },
            )
            return

        # Phase 9 MVP：先做模拟执行
        result = await self._simulate_agent_execution(
            agent=agent,
            task_id=task_id,
            input_payload=input_payload,
            metadata=metadata,
            required_capability=required_capability,
        )

        await self.data_bus.task_completed(
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            result=result,
            extra={
                "selected_agent_id": agent.get("id"),
                "selected_agent_name": agent.get("name"),
                "route_to": route_to,
            },
        )

    async def _get_agent_by_id(
        self,
        *,
        tenant_id: Optional[str],
        agent_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not agent_id:
            return None

        agents = await self.agent_registry.list_agents(tenant_id=tenant_id)
        for agent in agents:
            if agent.get("id") == agent_id:
                return agent
        return None

    async def _simulate_agent_execution(
        self,
        *,
        agent: Dict[str, Any],
        task_id: str,
        input_payload: Any,
        metadata: Dict[str, Any],
        required_capability: Optional[str],
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.05)

        return {
            "execution_mode": "simulated",
            "task_id": task_id,
            "agent_id": agent.get("id"),
            "agent_name": agent.get("name"),
            "required_capability": required_capability,
            "input": input_payload,
            "metadata": metadata,
            "output": {
                "message": "Agent execution completed",
            },
        }