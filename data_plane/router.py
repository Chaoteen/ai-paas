from __future__ import annotations

import asyncio
import logging
from typing import Optional

from data_plane.envelope import ExecutionEnvelope
from data_plane.result import ExecutionResult
from data_plane.handlers.agent_handler import AgentHandler
from data_plane.handlers.model_handler import ModelHandler
from data_plane.handlers.promptflow_handler import PromptflowHandler

logger = logging.getLogger(__name__)


class DataPlaneRouter:
    """
    Data Plane Router

    职责：
    - 根据 envelope.target_type 选择对应 handler
    - 不再做授权判断，授权已在 Control Plane 完成
    - 返回统一的 ExecutionResult
    """

    def __init__(
        self,
        *,
        agent_handler: Optional[AgentHandler],
        model_handler: Optional[ModelHandler],
        promptflow_handler: Optional[PromptflowHandler],
    ):
        self.agent_handler = agent_handler
        self.model_handler = model_handler
        self.promptflow_handler = promptflow_handler

    async def execute(
        self,
        envelope: ExecutionEnvelope,
        timeout_s: float = 15.0,
    ) -> ExecutionResult:
        try:
            if envelope.target_type == "agent":
                handler = self.agent_handler
            elif envelope.target_type == "model":
                handler = self.model_handler
            elif envelope.target_type == "promptflow":
                handler = self.promptflow_handler
            else:
                return ExecutionResult.error_result(
                    error=f"UNKNOWN_TARGET_TYPE: {envelope.target_type}",
                    metadata={
                        "router": "data_plane",
                        "target_type": envelope.target_type,
                    },
                )

            if handler is None:
                return ExecutionResult.error_result(
                    error=f"HANDLER_NOT_AVAILABLE: {envelope.target_type}",
                    metadata={
                        "router": "data_plane",
                        "target_type": envelope.target_type,
                    },
                )

            result = await asyncio.wait_for(
                handler.handle(envelope),
                timeout=timeout_s,
            )

            if isinstance(result, ExecutionResult):
                return result

            if isinstance(result, dict):
                ok = bool(
                    result.get("ok")
                    if "ok" in result
                    else result.get("success", result.get("status") == "success")
                )
                return ExecutionResult(
                    ok=ok,
                    output=result.get("output"),
                    error=result.get("error"),
                    metrics=result.get("metrics", {}) or {},
                    metadata=result.get("metadata", {}) or {},
                )

            return ExecutionResult.success_result(output=result)

        except asyncio.TimeoutError:
            return ExecutionResult.error_result(
                error="EXECUTION_TIMEOUT",
                metadata={"router": "data_plane"},
            )
        except Exception as e:
            logger.exception("DataPlaneRouter execution failed")
            return ExecutionResult.error_result(
                error=str(e),
                metadata={"router": "data_plane"},
            )