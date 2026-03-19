"""
LEGACY COMPATIBILITY MODULE

Status:
- Frozen for formal-release governance
- Not part of the formal Gateway -> Tasks API -> Task Store/Outbox -> Redis Queue -> Runtime Workers mainline
- Retained temporarily for historical reference / migration audit only

Rules:
- No new features
- No new production dependencies
- Do not wire this module into formal bootstrap/startup paths
- Candidate for archive/legacy migration after dependency cleanup
"""

# ai-os/data_plane/handlers/agent_handler.py
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from data_plane.envelope import ExecutionEnvelope
from data_plane.result import ExecutionResult
from data_plane.adapters.agent_core_adapter import AgentCoreAdapter


class AgentHandler:
    """
    同步 Agent 执行（通过 agent_core redis 流）
    """

    def __init__(self, adapter: AgentCoreAdapter):
        self.adapter = adapter

    async def handle(self, envelope: ExecutionEnvelope) -> ExecutionResult:
        started_at = time.time()
        try:
            session_id = envelope.context.get("session_id") or envelope.payload.get("session_id") or f"sess_{envelope.request_id}"
            task_id = envelope.context.get("task_id") or envelope.payload.get("task_id") or f"task_{envelope.request_id}"
            message_seq = int(envelope.context.get("message_seq") or envelope.payload.get("message_seq") or 0)

            # 将 Data Plane 的 agent 目标，交给你现有 router_bridge 的输入流
            result_env = await self.adapter.submit_and_wait(
                envelope_id=envelope.envelope_id,
                request_id=envelope.request_id,
                tenant_id=envelope.tenant_id,
                topic="prompt.execute",  # router_bridge 只要能解析 topic/data 即可
                data={
                    "content": envelope.payload.get("user_message", ""),
                    "task_type": envelope.payload.get("task_type", "general"),
                    "target_type": "agent",
                    "target": envelope.target,
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
                metrics={"handler": "agent", "target": envelope.target},
                started_at=started_at,
            )
        except Exception as e:
            return ExecutionResult.fail(
                envelope_id=envelope.envelope_id,
                request_id=envelope.request_id,
                tenant_id=envelope.tenant_id,
                error=str(e),
                metrics={"handler": "agent", "target": envelope.target},
                started_at=started_at,
            )
