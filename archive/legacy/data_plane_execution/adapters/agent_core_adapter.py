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

# ai-os/data_plane/adapters/agent_core_adapter.py
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import redis.asyncio as redis


@dataclass(frozen=True)
class AgentCoreAdapterConfig:
    redis_url: str = "redis://localhost:6379"

    # 输入流：router_bridge 监听的流
    request_stream: str = "agent.tasks.stream"

    # 输出流：task_manager / model_service 发布结果的流
    result_stream: str = "agent.result.stream"

    # XREAD block
    result_block_ms: int = 2000

    # 同步等待超时（秒）
    timeout_s: int = 60


class AgentCoreAdapter:
    """
    Data Plane -> agent_core 适配器（同步语义）

    做两件事：
    1) 把标准化 envelope 投递到 agent.tasks.stream（router_bridge 消费）
    2) 同步等待 agent.result.stream 返回匹配结果

    匹配优先级：
    - envelope_id（若下游透传）
    - request_id（若下游透传）
    - task_id（兜底）
    """

    def __init__(self, config: Optional[AgentCoreAdapterConfig] = None):
        self.cfg = config or AgentCoreAdapterConfig()
        self.redis = redis.from_url(self.cfg.redis_url, decode_responses=True)

    async def close(self):
        await self.redis.aclose()

    async def submit_and_wait(
        self,
        *,
        envelope_id: str,
        request_id: str,
        tenant_id: str,
        topic: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any],
        session_id: str,
        task_id: str,
        message_seq: int,
        timeout_s: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        同步提交并等待结果（返回 result_envelope 的 data 字段或完整结构，视需要而定）
        """
        timeout_s = timeout_s or self.cfg.timeout_s
        started_at = time.time()

        # 1) 写入请求流（router_bridge 消费）
        request_envelope = {
            "topic": topic,
            "data": {
                **data,
                # 强制透传（用于 sync match / multi-tenant）
                "tenant_id": tenant_id,
                "request_id": request_id,
                "envelope_id": envelope_id,
                "session_id": session_id,
                "task_id": task_id,
                "message_seq": message_seq,
            },
            "metadata": {
                **(metadata or {}),
                # metadata 内也兜底一份（便于下游取）
                "tenant_id": tenant_id,
                "request_id": request_id,
                "envelope_id": envelope_id,
                "session_id": session_id,
                "task_id": task_id,
                "message_seq": message_seq,
            },
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
            # 顶层也放一份（标准化）
            "tenant_id": tenant_id,
            "request_id": request_id,
            "envelope_id": envelope_id,
            "session_id": session_id,
            "task_id": task_id,
            "message_seq": message_seq,
        }

        await self.redis.xadd(
            self.cfg.request_stream,
            {"message": json.dumps(request_envelope)},
            maxlen=10000,
        )

        # 2) 同步等待结果（XREAD 从 $ 开始，只读新消息）
        #    注意：这是“同步等待”的 simplest 实现（每次请求一个等待循环）
        #    若你后续高并发，需要改成共享 consumer group + correlation map。
        last_id = "$"
        while True:
            if time.time() - started_at > timeout_s:
                raise TimeoutError(f"Wait result timeout after {timeout_s}s, task_id={task_id}")

            msgs = await self.redis.xread(
                streams={self.cfg.result_stream: last_id},
                count=50,
                block=self.cfg.result_block_ms,
            )
            if not msgs:
                continue

            for _stream, items in msgs:
                for msg_id, fields in items:
                    last_id = msg_id
                    raw = fields.get("message")
                    if not raw:
                        continue

                    try:
                        env = json.loads(raw)
                    except Exception:
                        continue

                    # 兼容：结果可能是 {topic,data,...} 或直接 data
                    env_data = env.get("data") if isinstance(env, dict) else None
                    if env_data is None and isinstance(env, dict):
                        env_data = env

                    # 匹配字段（优先 envelope_id/request_id，再兜底 task_id）
                    match = False
                    if isinstance(env, dict):
                        if env.get("envelope_id") == envelope_id or env.get("request_id") == request_id:
                            match = True
                    if not match and isinstance(env_data, dict):
                        if env_data.get("envelope_id") == envelope_id or env_data.get("request_id") == request_id:
                            match = True
                    if not match and isinstance(env_data, dict):
                        if env_data.get("task_id") == task_id and env_data.get("session_id") == session_id:
                            match = True

                    if match:
                        return env  # 返回完整结果 envelope（上层可取 env["data"]["result"] 等）
