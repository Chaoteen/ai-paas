from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from data_plane.envelope import ExecutionEnvelope
from data_plane.result import ExecutionResult
from data_plane.handlers.agent_handler import AgentHandler
from data_plane.handlers.model_handler import ModelHandler
from data_plane.handlers.promptflow_handler import PromptflowHandler
from data_plane.data_bus import DataBus

logger = logging.getLogger(__name__)


class DataPlaneRouter:
    def __init__(
        self,
        *,
        agent_handler: Optional[AgentHandler],
        model_handler: Optional[ModelHandler],
        promptflow_handler: Optional[PromptflowHandler],
        data_bus: Optional[DataBus] = None,
    ):
        self.agent_handler = agent_handler
        self.model_handler = model_handler
        self.promptflow_handler = promptflow_handler
        self.data_bus = data_bus or DataBus()

    def _build_task_id(self, envelope: ExecutionEnvelope) -> str:
        return f"task_{uuid.uuid4().hex}"

    async def execute(
        self,
        envelope: ExecutionEnvelope,
        timeout_s: float = 15.0,
    ) -> ExecutionResult:
        task_id = self._build_task_id(envelope)

        await self.data_bus.publish(
            event_type="task.created",
            task_id=task_id,
            payload={
                "request_id": envelope.request_id,
                "tenant_id": envelope.tenant_id,
                "target_type": envelope.target_type,
                "target": envelope.target,
                "envelope_id": envelope.envelope_id,
            },
        )

        try:
            if envelope.target_type == "agent":
                handler = self.agent_handler
            elif envelope.target_type == "model":
                handler = self.model_handler
            elif envelope.target_type == "promptflow":
                handler = self.promptflow_handler
            else:
                result = ExecutionResult.error_result(
                    error=f"UNKNOWN_TARGET_TYPE: {envelope.target_type}",
                    metadata={
                        "router": "data_plane",
                        "target_type": envelope.target_type,
                    },
                )
                await self.data_bus.publish(
                    event_type="task.failed",
                    task_id=task_id,
                    payload={
                        "error": result.error,
                        "target_type": envelope.target_type,
                        "envelope_id": envelope.envelope_id,
                    },
                )
                return result

            if handler is None:
                result = ExecutionResult.error_result(
                    error=f"HANDLER_NOT_AVAILABLE: {envelope.target_type}",
                    metadata={
                        "router": "data_plane",
                        "target_type": envelope.target_type,
                    },
                )
                await self.data_bus.publish(
                    event_type="task.failed",
                    task_id=task_id,
                    payload={
                        "error": result.error,
                        "target_type": envelope.target_type,
                        "envelope_id": envelope.envelope_id,
                    },
                )
                return result

            await self.data_bus.publish(
                event_type="task.dispatched",
                task_id=task_id,
                payload={
                    "target_type": envelope.target_type,
                    "target": envelope.target,
                    "envelope_id": envelope.envelope_id,
                },
            )

            result = await asyncio.wait_for(
                handler.handle(envelope),
                timeout=timeout_s,
            )

            if isinstance(result, ExecutionResult):
                normalized = result
            elif isinstance(result, dict):
                ok = bool(
                    result.get("ok")
                    if "ok" in result
                    else result.get("success", result.get("status") == "success")
                )
                normalized = ExecutionResult(
                    ok=ok,
                    output=result.get("output"),
                    error=result.get("error"),
                    metrics=result.get("metrics", {}) or {},
                    metadata=result.get("metadata", {}) or {},
                )
            else:
                normalized = ExecutionResult.success_result(output=result)

            if normalized.ok:
                await self.data_bus.publish(
                    event_type="task.completed",
                    task_id=task_id,
                    payload={
                        "target_type": envelope.target_type,
                        "target": envelope.target,
                        "status": normalized.status,
                        "envelope_id": envelope.envelope_id,
                    },
                )
            else:
                await self.data_bus.publish(
                    event_type="task.failed",
                    task_id=task_id,
                    payload={
                        "target_type": envelope.target_type,
                        "target": envelope.target,
                        "error": normalized.error,
                        "envelope_id": envelope.envelope_id,
                    },
                )

            return normalized

        except asyncio.TimeoutError:
            result = ExecutionResult.error_result(
                error="EXECUTION_TIMEOUT",
                metadata={"router": "data_plane"},
            )
            await self.data_bus.publish(
                event_type="task.failed",
                task_id=task_id,
                payload={
                    "error": result.error,
                    "target_type": envelope.target_type,
                    "envelope_id": envelope.envelope_id,
                },
            )
            return result

        except Exception as e:
            logger.exception("DataPlaneRouter execution failed")
            result = ExecutionResult.error_result(
                error=str(e),
                metadata={"router": "data_plane"},
            )
            await self.data_bus.publish(
                event_type="task.failed",
                task_id=task_id,
                payload={
                    "error": result.error,
                    "target_type": envelope.target_type,
                    "envelope_id": envelope.envelope_id,
                },
            )
            return result