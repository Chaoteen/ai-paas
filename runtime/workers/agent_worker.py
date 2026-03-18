from __future__ import annotations

import uuid
from typing import Any, Dict

from runtime.execution_context import ExecutionContext
from runtime.queue.task_models import AgentTaskPayload, TaskEnvelope
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import InMemoryTaskStore
from runtime.workers.worker_base import WorkerBase


class AgentWorker(WorkerBase):
    def __init__(
        self,
        *,
        queue_client: RedisStreamQueueClient,
        task_store: InMemoryTaskStore,
        agent_runtime: Any,
        consumer_name: str = "agent-worker-1",
    ) -> None:
        super().__init__(
            queue_client=queue_client,
            task_store=task_store,
            queue_name="agent",
            consumer_name=consumer_name,
        )
        self.agent_runtime = agent_runtime

    async def process_task(self, task: TaskEnvelope) -> Dict[str, Any]:
        payload = task.payload
        if not isinstance(payload, AgentTaskPayload):
            raise TypeError("AgentWorker received non-agent task payload")

        context = ExecutionContext(
            task_id=task.task_id,
            tenant_id=payload.tenant_id or task.tenant_id or "dev",
            workflow_id=payload.workflow_id or task.workflow_id,
            correlation_id=payload.correlation_id or task.correlation_id or str(uuid.uuid4()),
            user_id=payload.user_id or task.user_id,
            selected_agent_id=payload.agent_id,
            required_capability=payload.required_capability,
            workspace_root=payload.workspace_root,
            requested_capabilities=list(payload.requested_capabilities),
            allowed_capabilities=list(payload.allowed_capabilities),
            secrets_scope=list(payload.secrets_scope),
            metadata={
                **dict(payload.metadata),
                "session_id": payload.session_id,
                "routing_policy": payload.routing_policy,
                "queue_name": task.queue_name,
                "worker_consumer": self.consumer_name,
            },
            input_payload=self._build_input_payload(payload.input),
        )

        preferred_skill = payload.preferred_skill or payload.agent_id
        execute = getattr(self.agent_runtime, "execute", None)
        if not callable(execute):
            raise RuntimeError("agent_runtime has no callable execute()")

        raw = await execute(context=context, preferred_skill=preferred_skill)
        return self._normalize_result(raw)

    @staticmethod
    def _build_input_payload(user_input: Any) -> Dict[str, Any]:
        if isinstance(user_input, dict):
            payload = dict(user_input)
            if "input" not in payload:
                payload["input"] = user_input
            if "text" not in payload and isinstance(payload.get("input"), str):
                payload["text"] = payload["input"]
            return payload

        if isinstance(user_input, str):
            return {
                "input": user_input,
                "text": user_input,
            }

        return {
            "input": user_input,
        }

    @staticmethod
    def _normalize_result(raw: Any) -> Dict[str, Any]:
        if hasattr(raw, "to_dict") and callable(raw.to_dict):
            raw = raw.to_dict()

        if isinstance(raw, dict):
            return raw

        return {"output": raw}