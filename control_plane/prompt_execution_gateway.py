# ai-os/control_plane/prompt_execution_gateway.py
#!/usr/bin/env python3
"""
Control Plane - Prompt Execution Gateway (Frozen)
- 构造冻结 ExecutionContext
- 调用 PolicyClient / PDP 得到冻结 PolicyDecision
- 将裁剪后的 envelope 委派给 Data Plane Router 执行
- 同步返回执行结果

说明：
- 该文件属于 Control Plane，建议放在 ai-os/control_plane/
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from aiohttp import web
from redis import asyncio as aioredis

# ======== Frozen Models (Control Plane) ========
from control_plane.context import ExecutionContext
from control_plane.decision import PolicyDecision

# ======== Policy Client (Control Plane) ========
# 你已确认 policy_engine.py 对应 control_plane/policy_client.py
from control_plane.policy_client import PolicyClient

# ======== Data Plane ========
from data_plane.envelope import ExecutionEnvelope
from data_plane.router import DataPlaneRouter
from data_plane.adapters.redis_stream_adapter import RedisStreamAdapter
from data_plane.handlers.agent_handler import AgentHandler
from data_plane.handlers.model_handler import ModelHandler
from data_plane.handlers.promptflow_handler import PromptflowHandler

# =========================
# 基础配置
# =========================

CONFIG = {
    "http_host": "0.0.0.0",
    "http_port": 8080,

    # Redis
    "redis_url": "redis://localhost:6379",

    # 同步等待结果超时（秒）
    "default_timeout_s": 15.0,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ControlPlaneGateway")


class PromptExecutionGateway:
    """
    冻结的 Control Plane 网关
    """

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

        # Control Plane: policy
        self.policy_client: Optional[PolicyClient] = None

        # Data Plane Router
        self.data_plane: Optional[DataPlaneRouter] = None

        # Data Plane Redis Adapter
        self.redis_adapter: Optional[RedisStreamAdapter] = None

    # ---------- lifecycle ----------

    async def init_connections(self):
        # Redis（Control Plane 自己的治理/计量/配额也可能用）
        self.redis = await aioredis.from_url(CONFIG["redis_url"], decode_responses=True)

        # Policy client（PDP/PEP 客户端）
        self.policy_client = PolicyClient(redis=self.redis)

        # Data Plane 适配层（复用 Redis streams）
        self.redis_adapter = RedisStreamAdapter(
            redis_url=CONFIG["redis_url"],
            # 这里和你现有链路对齐：
            # - 发布到 agent.tasks.stream（router_bridge 消费）
            tasks_stream="agent.tasks.stream",
            # - 等待 agent.result.stream（task_manager/model_service 发布）
            results_stream="agent.result.stream",
            consumer_group="control_plane_gateway",
        )
        await self.redis_adapter.start()

        # Data Plane handlers
        agent_handler = AgentHandler(self.redis_adapter)
        model_handler = ModelHandler(self.redis_adapter)
        promptflow_handler = PromptflowHandler(self.redis_adapter)

        # Data Plane router
        self.data_plane = DataPlaneRouter(
            agent_handler=agent_handler,
            model_handler=model_handler,
            promptflow_handler=promptflow_handler,
        )

        logger.info("Control Plane connections initialized")

    async def close_connections(self):
        try:
            if self.redis_adapter:
                await self.redis_adapter.stop()
        finally:
            if self.redis:
                await self.redis.close()

    # ---------- Frozen Context Build ----------

    def build_execution_context(self, request_data: Dict[str, Any]) -> ExecutionContext:
        request_id = f"req_{uuid.uuid4().hex}"

        subject = {
            "type": request_data.get("subject_type", "user"),
            "id": request_data.get("user_id"),
            "tenant_id": request_data.get("tenant_id"),
            "attributes": request_data.get("user_attributes", {}),
        }

        action = request_data.get("action", "prompt.execute")

        resource = {
            "type": "prompt",
            "id": request_data.get("resource_id", "default"),
            "attributes": request_data.get("resource_attributes", {}),
        }

        environment = {
            "region": request_data.get("region", "default"),
            "compliance": request_data.get("compliance", []),
            "timestamp": datetime.utcnow().isoformat(),
            "source": request_data.get("request_source", "unknown"),
        }

        input_payload = request_data.get("input", {})

        return ExecutionContext(
            request_id=request_id,
            subject=subject,
            action=action,
            resource=resource,
            environment=environment,
            input_payload=input_payload,
        )

    # ---------- Quota / Usage ----------

    async def check_quota(self, tenant_id: str) -> bool:
        # 预留：可扩展为 tenant daily limits / tokens limits
        return True

    async def record_usage(self, tenant_id: str, tokens: int):
        # 用 Redis 做简单计量：usage:{tenant}:{yyyymmdd}
        key = f"usage:{tenant_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        await self.redis.hincrby(key, "requests", 1)
        await self.redis.hincrby(key, "tokens", int(tokens or 0))

    # ---------- Delegate to Data Plane ----------

    def _select_target(self, ctx: ExecutionContext, decision: PolicyDecision) -> Dict[str, str]:
        """
        决定 Data Plane 执行目标：
        - 优先采用 input.target_type / input.target（调用者显式指定）
        - 否则使用 policy.capabilities.allowed_agents 的第一个
        """
        inp = ctx.input or {}
        target_type = inp.get("target_type") or "agent"

        # target 选择规则：
        # - model: 默认用 policy.allowed_models[0]，否则用 input.target
        # - agent: 默认用 policy.allowed_agents[0]
        # - promptflow: 默认用 input.target（比如 flow_id），没有就走 "pf.default"
        policy_caps = (decision.capabilities or {})
        allowed_agents = policy_caps.get("allowed_agents") or ["agent.default"]
        allowed_models = policy_caps.get("allowed_models") or ["deepseek-r1-14b"]

        if target_type == "model":
            target = inp.get("target") or allowed_models[0]
        elif target_type == "promptflow":
            target = inp.get("target") or "pf.default"
        else:
            target_type = "agent"
            target = inp.get("target") or allowed_agents[0]

        return {"target_type": target_type, "target": target}

    def _build_execution_envelope(
        self,
        ctx: ExecutionContext,
        decision: PolicyDecision,
        target_type: str,
        target: str,
    ) -> ExecutionEnvelope:
        """
        Control Plane -> Data Plane 的裁剪封装（冻结边界）
        """
        envelope_id = f"env_{uuid.uuid4().hex}"

        return ExecutionEnvelope(
            envelope_id=envelope_id,
            request_id=ctx.request_id,
            tenant_id=ctx.subject.get("tenant_id"),
            subject=ctx.subject,
            action=ctx.action,
            resource=ctx.resource,
            environment=ctx.environment,
            target_type=target_type,
            target=target,
            payload=ctx.input,  # Data Plane 只用 input，不拿全 ctx
            context={
                # 只透传 policy 决策结果（冻结）
                "policy": decision.to_dict(),
                # 可选：会话配置（冻结）
                "session_context": ctx.input.get("session_context", {}),
                # 可选：agent_profile（冻结）
                "agent_profile": ctx.input.get("agent_profile", {}),
            },
            created_at=datetime.utcnow().timestamp(),
        )

    async def delegate_execution(self, ctx: ExecutionContext, decision: PolicyDecision) -> Dict[str, Any]:
        if not self.data_plane:
            raise RuntimeError("DataPlaneRouter not initialized")

        target_sel = self._select_target(ctx, decision)
        target_type = target_sel["target_type"]
        target = target_sel["target"]

        env = self._build_execution_envelope(ctx, decision, target_type, target)

        timeout_s = float((ctx.input or {}).get("timeout_s") or CONFIG["default_timeout_s"])

        result = await self.data_plane.execute(env, timeout_s=timeout_s)

        return {
            "envelope_id": env.envelope_id,
            "target_type": target_type,
            "target": target,
            "status": result.status,
            "output": result.output,
            "error": result.error,
            "metrics": result.metrics,
        }

    # ---------- HTTP Handlers ----------

    async def execute(self, request: web.Request) -> web.Response:
        start_time = datetime.utcnow()

        try:
            if not self.policy_client:
                raise RuntimeError("PolicyClient not initialized")

            request_data = await request.json()
            ctx = self.build_execution_context(request_data)

            # 1) Authorize (PEP -> PDP)
            decision = await self.policy_client.authorize(ctx)

            if not decision.allow:
                return web.json_response(
                    {
                        "error": "ACCESS_DENIED",
                        "reason": decision.reason,
                        "request_id": ctx.request_id,
                    },
                    status=403,
                )

            tenant_id = ctx.subject.get("tenant_id")
            if not tenant_id:
                return web.json_response(
                    {
                        "error": "TENANT_REQUIRED",
                        "request_id": ctx.request_id,
                    },
                    status=400,
                )

            # 2) Quota
            if not await self.check_quota(tenant_id):
                return web.json_response({"error": "QUOTA_EXCEEDED"}, status=429)

            # 3) Delegate to Data Plane (sync-wait)
            dp_result = await self.delegate_execution(ctx, decision)

            # 4) Usage record（如果 output 里有 tokens）
            tokens_used = 0
            try:
                out = dp_result.get("output") or {}
                raw = out.get("raw") if isinstance(out, dict) else {}
                usage = raw.get("token_usage") if isinstance(raw, dict) else None
                if isinstance(usage, dict):
                    tokens_used = int(usage.get("total_tokens") or 0)
            except Exception:
                tokens_used = 0

            await self.record_usage(tenant_id, tokens_used)

            return web.json_response(
                {
                    "request_id": ctx.request_id,
                    "policy": decision.to_dict(),
                    "data_plane": dp_result,
                    "processing_time": (datetime.utcnow() - start_time).total_seconds(),
                }
            )

        except Exception as e:
            logger.exception("Execution failed")
            return web.json_response(
                {"error": "INTERNAL_ERROR", "message": str(e)},
                status=500,
            )

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "healthy",
                "service": "control-plane-gateway",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


def create_app():
    gateway = PromptExecutionGateway()
    app = web.Application()

    app.router.add_post("/v1/execute", gateway.execute)
    app.router.add_get("/health", gateway.health)

    async def _startup(app_: web.Application):
        await gateway.init_connections()

    async def _cleanup(app_: web.Application):
        await gateway.close_connections()

    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)

    return app


async def main():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        CONFIG["http_host"],
        CONFIG["http_port"],
    )
    await site.start()

    logger.info(
        "Control Plane Gateway running on %s:%s",
        CONFIG["http_host"],
        CONFIG["http_port"],
    )

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
