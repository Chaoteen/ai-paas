# ai-os/data_plane/router.py
from __future__ import annotations

import time
from typing import Optional

from data_plane.envelope import ExecutionEnvelope
from data_plane.result import ExecutionResult
from data_plane.handlers.agent_handler import AgentHandler
from data_plane.handlers.model_handler import ModelHandler
from data_plane.handlers.promptflow_handler import PromptflowHandler


class DataPlaneRouter:
    """
    Data Plane 同步路由器（最终版）

    输入：ExecutionEnvelope（冻结）
    输出：ExecutionResult（同步）

    说明：
    - 不做授权判断（Control Plane 已裁决）
    - 不修改 envelope（只读）
    - 根据 target_type 分发到 handler
    """

    def __init__(
        self,
        *,
        agent_handler: AgentHandler,
        model_handler: ModelHandler,
        promptflow_handler: PromptflowHandler,
    ):
        self.agent_handler = agent_handler
        self.model_handler = model_handler
        self.promptflow_handler = promptflow_handler

    async def execute(self, envelope: ExecutionEnvelope) -> ExecutionResult:
        started_at = time.time()

        if envelope.target_type == "agent":
            r = await self.agent_handler.handle(envelope)
        elif envelope.target_type == "model":
            r = await self.model_handler.handle(envelope)
        elif envelope.target_type == "promptflow":
            r = await self.promptflow_handler.handle(envelope)
        else:
            r = ExecutionResult.fail(
                envelope_id=envelope.envelope_id,
                request_id=envelope.request_id,
                tenant_id=envelope.tenant_id,
                error=f"UNKNOWN_TARGET_TYPE: {envelope.target_type}",
                metrics={"router": "data_plane"},
                started_at=started_at,
            )

        return r
