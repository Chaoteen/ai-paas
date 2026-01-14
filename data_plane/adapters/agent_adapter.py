# D:\RD\ai-os\data_plane\adapters\agent_adapter.py
import json
import time
import uuid
import logging
from typing import Any, Dict, Optional

from .redis_client import RedisAsyncClient

logger = logging.getLogger("AgentAdapter")


class AgentAdapter:
    """
    将 Data Plane ExecutionEnvelope 投递到 agent.tasks.stream
    由你现有 router_bridge.py 消费并继续处理（过渡期最稳）
    """

    def __init__(
        self,
        redis_client: RedisAsyncClient,
        stream_name: str = "agent.tasks.stream",
        maxlen: int = 10000,
    ):
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.maxlen = maxlen

    def _build_legacy_envelope(self, execution_envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 Control Plane 的结构裁剪成 router_bridge 最易兼容的 envelope
        """
        ctx = execution_envelope.get("context", {}) or {}
        policy = execution_envelope.get("policy", {}) or {}
        inp = execution_envelope.get("input", {}) or {}

        tenant_id = execution_envelope.get("tenant_id") or ctx.get("subject", {}).get("tenant_id")

        # router_bridge 会从 topic/data 里抽取 content/task_type 等
        data = {
            "session_id": inp.get("session_id") or ctx.get("request_id"),
            "task_id": inp.get("task_id") or f"task_{uuid.uuid4().hex}",
            "content": inp.get("user_message") or inp.get("content") or "",
            "task_type": inp.get("task_type") or "general",

            # 多租户/权限（router_bridge 会提取 metadata）
            "tenant_id": tenant_id,
            "user_id": ctx.get("subject", {}).get("id"),
            "permissions": ctx.get("subject", {}).get("attributes", {}).get("permissions", []),

            # agent/model 策略（用于路由与模型选择）
            "subscribed_agents": policy.get("capabilities", {}).get("allowed_agents", ["agent.default"]),
            "model": policy.get("capabilities", {}).get("allowed_models", [None])[0],
            "fallback_models": policy.get("capabilities", {}).get("allowed_models", [])[1:],
            "temperature": policy.get("capabilities", {}).get("temperature", 0.2),
        }

        return {
            "topic": "agent.tasks.stream",
            "data": data,
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
            # 关键：避免 router_bridge 的防循环误判
            "routed_by": None,
        }

    async def dispatch(self, execution_envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        投递到 agent.tasks.stream，返回投递确认信息
        """
        await self.redis_client.connect()
        legacy_env = self._build_legacy_envelope(execution_envelope)

        msg_str = json.dumps(legacy_env, ensure_ascii=False)
        message_id = await self.redis_client.client.xadd(
            self.stream_name,
            {"message": msg_str},
            maxlen=self.maxlen,
        )

        logger.info(f"Dispatched to {self.stream_name} message_id={message_id}")
        return {
            "status": "queued",
            "stream": self.stream_name,
            "message_id": message_id,
        }
