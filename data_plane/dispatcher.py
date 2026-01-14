# ai-os/data_plane/dispatcher.py

import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable

from data_plane.envelope import ExecutionEnvelope, validate_envelope
from agent_core.envelope_bus import MessageBus
from data_plane.result import ExecutionResult

logger = logging.getLogger("DataPlaneDispatcher")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


class DataPlaneDispatcher:
    """
    Data Plane 冻结调度器

    职责边界（非常重要）：
    - 只接受 Control Plane 下发的 ExecutionEnvelope
    - 不做权限判断、不做配额判断、不修改 envelope
    - 根据 action 路由到不同执行通道
    """

    def __init__(self):
        self.bus = MessageBus.get_instance()
        self._handlers: Dict[str, Callable[[ExecutionEnvelope], Awaitable[ExecutionResult]]] = {}

    # =========================
    # 注册执行通道
    # =========================

    def register_handler(
        self,
        action: str,
        handler: Callable[[ExecutionEnvelope], Awaitable[ExecutionResult]],
    ):
        """
        注册 action -> handler 的映射

        示例：
        - agent.run
        - model.inference
        - promptflow.execute
        """
        if action in self._handlers:
            raise RuntimeError(f"Handler already registered for action: {action}")

        self._handlers[action] = handler
        logger.info(f"Registered handler for action: {action}")

    # =========================
    # 主入口
    # =========================

    async def dispatch(self, envelope: ExecutionEnvelope) -> ExecutionResult:
        """
        Data Plane 统一执行入口
        """

        logger.info(
            f"Dispatching envelope "
            f"id={envelope.envelope_id} "
            f"tenant={envelope.tenant_id} "
            f"action={envelope.action}"
        )

        # --- 1. Envelope 结构校验（不做策略判断） ---
        validate_envelope(envelope)

        # --- 2. 路由 ---
        handler = self._handlers.get(envelope.action)
        if not handler:
            logger.error(f"No handler for action: {envelope.action}")
            return ExecutionResult(
                envelope_id=envelope.envelope_id,
                success=False,
                error=f"UNSUPPORTED_ACTION: {envelope.action}",
            )

        # --- 3. 执行 ---
        try:
            result = await handler(envelope)
        except Exception as e:
            logger.exception("Execution failed in handler")
            return ExecutionResult(
                envelope_id=envelope.envelope_id,
                success=False,
                error=str(e),
            )

        # --- 4. 发布执行完成事件（异步，不阻塞） ---
        await self.bus.publish(
            topic="execution.finished",
            message={
                "envelope_id": envelope.envelope_id,
                "tenant_id": envelope.tenant_id,
                "action": envelope.action,
                "success": result.success,
            },
        )

        return result

    # =========================
    # 生命周期
    # =========================

    async def start(self):
        """
        启动 Data Plane（主要是 MessageBus）
        """
        logger.info("Starting Data Plane Dispatcher")
        asyncio.create_task(self.bus.start())
