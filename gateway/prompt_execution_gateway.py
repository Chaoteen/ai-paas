# ai-os/gateway/prompt_execution_gateway.py

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from aiohttp import web

from control_plane.context import ExecutionContext
from control_plane.decision import PolicyDecision
from control_plane.policy_client import PolicyClient

from data_plane.envelope import ExecutionEnvelope
from data_plane.router import DataPlaneRouter

from data_plane.handlers.agent_handler import AgentHandler
from data_plane.handlers.model_handler import ModelHandler
from data_plane.handlers.promptflow_handler import PromptFlowHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("Gateway")

CONFIG = {
    "http_host": "0.0.0.0",
    "http_port": 8080,

    # Data Plane deps
    "redis_url": "redis://localhost:6379",
    "promptflow_score_url": "http://localhost:8081/score",
    "model_gateway_base": "http://localhost:8090",

    # sync timeout
    "agent_timeout_s": 30,
    "model_timeout_s": 60,
    "promptflow_timeout_s": 30,
}


class PromptExecutionGateway:
    """
    对外 HTTP 网关（同步语义）
    - 构建冻结 ExecutionContext
    - 调用 PolicyClient -> PolicyDecision
    - 构建冻结 ExecutionEnvelope
    - 调用 DataPlaneRouter.execute -> ExecutionResult
    - 一次请求内返回
    """

    def __init__(self):
        self.policy_client = PolicyClient()
        self.router = self._build_data_plane_router()

    def _build_data_plane_router(self) -> DataPlaneRouter:
        agent_handler = AgentHandler(
            redis_url=CONFIG["redis_url"],
            timeout_seconds=CONFIG["agent_timeout_s"],
        )
        model_handler = ModelHandler(
            base_url=CONFIG["model_gateway_base"],
            timeout_seconds=CONFIG["model_timeout_s"],
        )
        promptflow_handler = PromptFlowHandler(
            score_url=CONFIG["promptflow_score_url"],
            timeout_seconds=CONFIG["promptflow_timeout_s"],
        )

        router = DataPlaneRouter(
            agent_handler=agent_handler,
            model_handler=model_handler,
            promptflow_handler=promptflow_handler,
        )
        return router

    def build_execution_context(self, request_data: Dict[str, Any]) -> ExecutionContext:
        # 冻结四元组
        subject = {
            "type": request_data.get("subject_type", "user"),
            "id": request_data.get("user_id"),
            "tenant_id": request_data.get("tenant_id"),
            "attributes": request_data.get("user_attributes", {}),
        }
        action = request_data.get("action", "prompt.execute")
        resource = {
            "type": request_data.get("resource_type", "prompt"),
            "id": request_data.get("resource_id", "default"),
            "attributes": request_data.get("resource_attributes", {}),
        }
        environment = {
            "region": request_data.get("region", "default"),
            "compliance": request_data.get("compliance", []),
            "timestamp": datetime.utcnow().isoformat(),
            "source": request_data.get("request_source", "unknown"),
        }

        return ExecutionContext(
            subject=subject,
            action=action,
            resource=resource,
            environment=environment,
            input_payload=request_data.get("input", {}),
        )

    def build_envelope(self, ctx: ExecutionContext, decision: PolicyDecision) -> ExecutionEnvelope:
        input_payload = ctx.input

        tenant_id = ctx.subject.get("tenant_id")
        request_id = ctx.request_id

        # target_type / target 由请求指定，或由 policy capabilities 限制
        target_type = input_payload.get("target_type", "agent")  # agent|model|promptflow
        target = input_payload.get("target", "agent.default")

        # capabilities 透传进 context（冻结扩展区）
        context = {
            "policy": decision.to_dict(),
            # 可附加：user_profile/agent_profile 等（与你 router_bridge 的metadata对齐）
            "user_profile": ctx.subject,
            "session_id": input_payload.get("session_id"),
            "task_id": input_payload.get("task_id"),
            "message_seq": input_payload.get("message_seq", 0),
        }

        payload = {
            # Data Plane 统一读 content / user_message
            "user_message": input_payload.get("user_message", ""),
            "content": input_payload.get("user_message", ""),
            "task_type": input_payload.get("task_type", "general"),

            # 可选增强字段
            "memory_hot": input_payload.get("memory_hot", []),
            "memory_cold": input_payload.get("memory_cold", []),
            "retrieved_docs": input_payload.get("retrieved_docs", []),
        }

        return ExecutionEnvelope.new(
            request_id=request_id,
            tenant_id=tenant_id,
            subject=ctx.subject,
            action=ctx.action,
            resource=ctx.resource,
            environment=ctx.environment,
            target_type=target_type,
            target=target,
            payload=payload,
            context=context,
        )

    async def execute(self, request: web.Request) -> web.Response:
        start = datetime.utcnow()

        try:
            request_data = await request.json()

            # 1) build frozen context
            ctx = self.build_execution_context(request_data)

            # 2) authorize (Control Plane)
            decision = await self.policy_client.authorize(ctx)
            if not decision.allow:
                return web.json_response(
                    {"error": "ACCESS_DENIED", "reason": decision.reason, "request_id": ctx.request_id},
                    status=403,
                )

            # 3) build frozen envelope
            env = self.build_envelope(ctx, decision)

            # 4) Data Plane execute (sync semantics)
            result = await self.router.execute(env)

            # 5) response
            if not result.success:
                return web.json_response(
                    {
                        "request_id": env.request_id,
                        "envelope_id": env.envelope_id,
                        "tenant_id": env.tenant_id,
                        "error": "EXECUTION_FAILED",
                        "message": result.error,
                        "metrics": result.metrics,
                        "processing_time": (datetime.utcnow() - start).total_seconds(),
                    },
                    status=500,
                )

            return web.json_response(
                {
                    "request_id": env.request_id,
                    "envelope_id": env.envelope_id,
                    "tenant_id": env.tenant_id,
                    "result": result.output,
                    "metrics": result.metrics,
                    "processing_time": (datetime.utcnow() - start).total_seconds(),
                }
            )

        except Exception as e:
            logger.exception("execute failed")
            return web.json_response({"error": "INTERNAL_ERROR", "message": str(e)}, status=500)

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "healthy", "service": "gateway", "timestamp": datetime.utcnow().isoformat()})


def create_app() -> web.Application:
    gw = PromptExecutionGateway()
    app = web.Application()
    app.router.add_post("/v1/execute", gw.execute)
    app.router.add_get("/health", gw.health)
    return app


async def main():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, CONFIG["http_host"], CONFIG["http_port"])
    await site.start()
    logger.info("Gateway running on %s:%s", CONFIG["http_host"], CONFIG["http_port"])
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
