from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from data_plane.data_bus import DATA_EVENTS_STREAM, DataBus
from data_plane.redis_stream_bus import RedisStreamBus
from runtime.agent_runtime import AgentRuntime
from runtime.execution_context import ExecutionContext
from runtime.idempotency import InMemoryIdempotencyStore, build_event_stage_key
from runtime.state_store import InMemoryRuntimeStateStore
from runtime.workflow_state import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_EXECUTING,
    TASK_STATUS_FAILED,
    TASK_STATUS_ROUTED,
)


class AgentWorker:
    """
    Phase 11-B:
    - 消费 router.success
    - 幂等保护，避免重复执行
    - 写入 task state
    - 发布 task.executing
    - 通过 AgentRuntime 执行
    - 发布 task.completed / task.failed
    """

    def __init__(
        self,
        *,
        agent_registry: Any,
        data_bus: DataBus,
        event_bus: RedisStreamBus,
        agent_runtime: AgentRuntime | None = None,
        state_store: InMemoryRuntimeStateStore | None = None,
        idempotency_store: InMemoryIdempotencyStore | None = None,
        consumer_group: str = "agent-workers",
        consumer_name: str = "agent-1",
    ) -> None:
        self.agent_registry = agent_registry
        self.data_bus = data_bus
        self.event_bus = event_bus
        self.agent_runtime = agent_runtime
        self.state_store = state_store
        self.idempotency_store = idempotency_store
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self._running = False

    async def start(self) -> None:
        await asyncio.to_thread(
            self.event_bus.ensure_group,
            DATA_EVENTS_STREAM,
            self.consumer_group,
        )
        self._running = True

        while self._running:
            messages = await asyncio.to_thread(
                self.event_bus.consume,
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
                    await asyncio.to_thread(
                        self.event_bus.ack,
                        msg.stream,
                        self.consumer_group,
                        msg.message_id,
                    )
                except Exception as exc:
                    await asyncio.to_thread(
                        self.event_bus.dead_letter,
                        original_stream=msg.stream,
                        envelope=msg.envelope,
                        reason=str(exc),
                    )
                    await asyncio.to_thread(
                        self.event_bus.ack,
                        msg.stream,
                        self.consumer_group,
                        msg.message_id,
                    )

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
        input_payload = extra.get("input") or {}
        metadata = extra.get("metadata", {}) or {}

        if not task_id:
            return

        if self.idempotency_store is not None:
            idem_key = build_event_stage_key(task_id=task_id, stage="executing")
            acquired = await self.idempotency_store.acquire(
                key=idem_key,
                owner=self.consumer_name,
            )
            if not acquired:
                return

        if self.state_store is not None:
            await self.state_store.create_task(
                task_id=task_id,
                tenant_id=tenant_id or "unknown-tenant",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                input_payload=input_payload,
                metadata=metadata,
            )
            await self.state_store.transition_task(
                task_id=task_id,
                new_status=TASK_STATUS_ROUTED,
                event_type="router.success",
                selected_agent_id=selected_agent_id,
                metadata_patch={
                    "route_to": route_to,
                    "selected_agent_name": selected_agent_name,
                },
            )

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

        if self.state_store is not None:
            await self.state_store.transition_task(
                task_id=task_id,
                new_status=TASK_STATUS_EXECUTING,
                event_type="task.executing",
                selected_agent_id=selected_agent_id,
            )

        agent = await self._get_agent_by_id(
            tenant_id=tenant_id,
            agent_id=selected_agent_id,
        )

        if agent is None:
            if self.state_store is not None:
                await self.state_store.transition_task(
                    task_id=task_id,
                    new_status=TASK_STATUS_FAILED,
                    event_type="task.failed",
                    selected_agent_id=selected_agent_id,
                    error="AGENT_NOT_FOUND",
                )

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

        if self.agent_runtime is None:
            result = await self._simulate_agent_execution(
                agent=agent,
                task_id=task_id,
                input_payload=input_payload,
                metadata=metadata,
                required_capability=required_capability,
            )

            if self.state_store is not None:
                await self.state_store.transition_task(
                    task_id=task_id,
                    new_status=TASK_STATUS_COMPLETED,
                    event_type="task.completed",
                    selected_agent_id=agent.get("id"),
                    output_payload=result,
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
            return

        context = ExecutionContext(
            task_id=task_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            selected_agent_id=agent.get("id"),
            required_capability=required_capability,
            input_payload=input_payload,
            metadata=metadata,
            allowed_capabilities=self._extract_allowed_capabilities(agent),
        )

        runtime_result = await self.agent_runtime.execute(context=context)

        if runtime_result.status != "completed":
            if self.state_store is not None:
                await self.state_store.transition_task(
                    task_id=task_id,
                    new_status=TASK_STATUS_FAILED,
                    event_type="task.failed",
                    selected_agent_id=agent.get("id"),
                    selected_skill=runtime_result.skill_name,
                    error=runtime_result.error or "AGENT_RUNTIME_FAILED",
                )

            await self.data_bus.task_failed(
                task_id=task_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                error=runtime_result.error or "AGENT_RUNTIME_FAILED",
                extra={
                    "selected_agent_id": agent.get("id"),
                    "selected_agent_name": agent.get("name"),
                    "route_to": route_to,
                    "skill_name": runtime_result.skill_name,
                    "skill_source": runtime_result.skill_source,
                },
            )
            return

        result_payload = {
            "execution_mode": "runtime",
            "task_id": task_id,
            "agent_id": agent.get("id"),
            "agent_name": agent.get("name"),
            "required_capability": required_capability,
            "input": input_payload,
            "metadata": metadata,
            "runtime": runtime_result.to_dict(),
            "output": runtime_result.output,
        }

        if self.state_store is not None:
            await self.state_store.transition_task(
                task_id=task_id,
                new_status=TASK_STATUS_COMPLETED,
                event_type="task.completed",
                selected_agent_id=agent.get("id"),
                selected_skill=runtime_result.skill_name,
                output_payload=result_payload,
            )

        await self.data_bus.task_completed(
            task_id=task_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            result=result_payload,
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

    def _extract_allowed_capabilities(self, agent: Dict[str, Any]) -> list[str]:
        direct = agent.get("allowed_capabilities")
        if isinstance(direct, list):
            return [str(x) for x in direct]

        metadata = agent.get("metadata", {}) or {}
        nested = metadata.get("allowed_capabilities")
        if isinstance(nested, list):
            return [str(x) for x in nested]

        return []

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