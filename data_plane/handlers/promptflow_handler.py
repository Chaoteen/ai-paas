# ai-os/data_plane/handlers/promptflow_handler.py
from __future__ import annotations

import time

from data_plane.envelope import ExecutionEnvelope
from data_plane.result import ExecutionResult
from data_plane.adapters.agent_core_adapter import AgentCoreAdapter


class PromptflowHandler:
    """
    同步 PromptFlow 执行（通过 agent_core pipeline 或独立 promptflow 服务均可）
    这里为了统一链路，仍走 agent_core 输入流，让 router_bridge 决定是否调用 promptflow。
    """

    def __init__(self, adapter: AgentCoreAdapter):
        self.adapter = adapter

    async def handle(self, envelope: ExecutionEnvelope) -> ExecutionResult:
        started_at = time.time()
        try:
            session_id = envelope.context.get("session_id") or envelope.payload.get("session_id") or f"sess_{envelope.request_id}"
            task_id = envelope.context.get("task_id") or envelope.payload.get("task_id") or f"task_{envelope.request_id}"
            message_seq = int(envelope.context.get("message_seq") or envelope.payload.get("message_seq") or 0)

            result_env = await self.adapter.submit_and_wait(
                envelope_id=envelope.envelope_id,
                request_id=envelope.request_id,
                tenant_id=envelope.tenant_id,
                topic="prompt.execute",
                data={
                    "content": envelope.payload.get("user_message", ""),
                    "task_type": envelope.payload.get("task_type", "general"),
                    "target_type": "promptflow",
                    "target": envelope.target,  # e.g. pf.default
                    "promptflow": envelope.target,
                },
                metadata={
                    "user_profile": envelope.subject.get("attributes", {}),
                    "agent_profile": envelope.context.get("agent_profile", {}),
                    "session_context": envelope.context.get("session_context", {}),
                },
                session_id=session_id,
                task_id=task_id,
                message_seq=message_seq,
            )

            return ExecutionResult.success(
                envelope_id=envelope.envelope_id,
                request_id=envelope.request_id,
                tenant_id=envelope.tenant_id,
                output=result_env,
                metrics={"handler": "promptflow", "target": envelope.target},
                started_at=started_at,
            )
        except Exception as e:
            return ExecutionResult.fail(
                envelope_id=envelope.envelope_id,
                request_id=envelope.request_id,
                tenant_id=envelope.tenant_id,
                error=str(e),
                metrics={"handler": "promptflow", "target": envelope.target},
                started_at=started_at,
            )
