#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from aiohttp import web
from redis import asyncio as aioredis

from control_plane.context import ExecutionContext
from control_plane.decision import PolicyDecision
from control_plane.policy_client import PolicyClient
from control_plane.agent_manifest import AgentManifest
from control_plane.agent_registry import AgentRegistry

from data_plane.envelope import ExecutionEnvelope
from data_plane.router import DataPlaneRouter
from data_plane.result import ExecutionResult


CONFIG = {
    "http_host": "0.0.0.0",
    "http_port": 8080,
    "redis_url": "redis://localhost:6379",
    "default_timeout_s": 15.0,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ControlPlaneGateway")


class PromptExecutionGateway:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.policy_client: Optional[PolicyClient] = None
        self.data_plane: Optional[DataPlaneRouter] = None
        self.redis_adapter: Optional[Any] = None
        self.agent_registry = AgentRegistry()

    def _import_runtime_class(self, module_name: str, class_name: str):
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except ModuleNotFoundError as e:
            raise RuntimeError(
                f"RUNTIME_DEPENDENCY_MISSING: module={module_name}, class={class_name}, detail={e}"
            ) from e
        except AttributeError as e:
            raise RuntimeError(
                f"RUNTIME_CLASS_MISSING: module={module_name}, class={class_name}, detail={e}"
            ) from e

    async def init_connections(self):
        self.redis = await aioredis.from_url(CONFIG["redis_url"], decode_responses=True)
        self.policy_client = PolicyClient(redis=self.redis)

        RedisStreamAdapter = self._import_runtime_class(
            "data_plane.adapters.redis_stream_adapter",
            "RedisStreamAdapter",
        )
        AgentHandler = self._import_runtime_class(
            "data_plane.handlers.agent_handler",
            "AgentHandler",
        )
        ModelHandler = self._import_runtime_class(
            "data_plane.handlers.model_handler",
            "ModelHandler",
        )
        PromptflowHandler = self._import_runtime_class(
            "data_plane.handlers.promptflow_handler",
            "PromptflowHandler",
        )

        self.redis_adapter = RedisStreamAdapter(
            redis_url=CONFIG["redis_url"],
            tasks_stream="agent.tasks.stream",
            results_stream="agent.result.stream",
            consumer_group="control_plane_gateway",
        )
        await self.redis_adapter.start()

        agent_handler = AgentHandler(self.redis_adapter)
        model_handler = ModelHandler(self.redis_adapter)
        promptflow_handler = PromptflowHandler(self.redis_adapter)

        self.data_plane = DataPlaneRouter(
            agent_handler=agent_handler,
            model_handler=model_handler,
            promptflow_handler=promptflow_handler,
        )
        logger.info("Control Plane connections initialized")

    async def close_connections(self):
        try:
            if self.redis_adapter and hasattr(self.redis_adapter, "stop"):
                await self.redis_adapter.stop()
        finally:
            if self.redis:
                await self.redis.close()

    def build_execution_context(self, request_data: Dict[str, Any]) -> ExecutionContext:
        return ExecutionContext.from_request_data(request_data)

    async def check_quota(self, tenant_id: str) -> bool:
        return True

    async def record_usage(self, tenant_id: str, tokens: int):
        if not self.redis:
            return
        key = f"usage:{tenant_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        await self.redis.hincrby(key, "requests", 1)
        await self.redis.hincrby(key, "tokens", int(tokens or 0))

    def _select_target(self, ctx: ExecutionContext, decision: PolicyDecision) -> Dict[str, str]:
        inp = ctx.input or {}
        target_type = inp.get("target_type") or "agent"

        policy_caps = decision.capabilities or {}
        allowed_agents = policy_caps.get("allowed_agents") or ["agent.default"]
        allowed_models = policy_caps.get("allowed_models") or ["deepseek-r1-14b"]
        allowed_promptflows = policy_caps.get("allowed_promptflows") or ["pf.default"]

        if target_type == "model":
            target = inp.get("target") or allowed_models[0]
        elif target_type == "promptflow":
            target = inp.get("target") or allowed_promptflows[0]
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
            payload=ctx.input,
            context={
                "policy": decision.to_dict(),
                "session_context": ctx.input.get("session_context", {}),
                "agent_profile": ctx.input.get("agent_profile", {}),
                "trace_id": ctx.trace_id,
                "session_id": ctx.session_id,
            },
            created_at=datetime.utcnow().timestamp(),
        )

    @staticmethod
    def _normalize_result(result: Any) -> ExecutionResult:
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

        return ExecutionResult.error_result(
            error=f"UNSUPPORTED_RESULT_TYPE: {type(result).__name__}"
        )

    async def delegate_execution(self, ctx: ExecutionContext, decision: PolicyDecision) -> Dict[str, Any]:
        if not self.data_plane:
            raise RuntimeError("DATA_PLANE_NOT_INITIALIZED")

        target_sel = self._select_target(ctx, decision)
        target_type = target_sel["target_type"]
        target = target_sel["target"]

        env = self._build_execution_envelope(ctx, decision, target_type, target)
        timeout_s = float((ctx.input or {}).get("timeout_s") or CONFIG["default_timeout_s"])

        raw_result = await self.data_plane.execute(env, timeout_s=timeout_s)
        result = self._normalize_result(raw_result)

        return {
            "envelope_id": env.envelope_id,
            "target_type": target_type,
            "target": target,
            **result.to_dict(),
        }

    async def execute(self, request: web.Request) -> web.Response:
        start_time = datetime.utcnow()
        try:
            if not self.policy_client:
                raise RuntimeError("POLICY_CLIENT_NOT_INITIALIZED")

            request_data = await request.json()
            ctx = self.build_execution_context(request_data)

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

            if not await self.check_quota(tenant_id):
                return web.json_response({"error": "QUOTA_EXCEEDED"}, status=429)

            dp_result = await self.delegate_execution(ctx, decision)

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

    async def register_agent(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            manifest = AgentManifest.from_dict(payload)
            record = self.agent_registry.register(manifest)

            return web.json_response(
                {
                    "ok": True,
                    "agent": record.to_dict(),
                },
                status=201,
            )
        except ValueError as e:
            return web.json_response(
                {
                    "ok": False,
                    "error": str(e),
                },
                status=400,
            )
        except Exception as e:
            logger.exception("Agent registration failed")
            return web.json_response(
                {
                    "ok": False,
                    "error": str(e),
                },
                status=500,
            )

    async def heartbeat_agent(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            agent_id = (payload.get("agent_id") or "").strip()
            if not agent_id:
                return web.json_response(
                    {"ok": False, "error": "AGENT_ID_REQUIRED"},
                    status=400,
                )

            record = self.agent_registry.heartbeat(agent_id)
            return web.json_response(
                {
                    "ok": True,
                    "agent": record.to_dict(),
                }
            )
        except KeyError as e:
            return web.json_response(
                {
                    "ok": False,
                    "error": str(e),
                },
                status=404,
            )
        except Exception as e:
            logger.exception("Agent heartbeat failed")
            return web.json_response(
                {
                    "ok": False,
                    "error": str(e),
                },
                status=500,
            )

    async def list_agents(self, request: web.Request) -> web.Response:
        records = [r.to_dict() for r in self.agent_registry.list_agents()]
        return web.json_response(
            {
                "ok": True,
                "agents": records,
                "count": len(records),
            }
        )

    async def list_control_events(self, request: web.Request) -> web.Response:
        event_type = request.query.get("event_type")
        aggregate_id = request.query.get("aggregate_id")

        events = [
            e.to_dict()
            for e in self.agent_registry.list_control_events(
                event_type=event_type,
                aggregate_id=aggregate_id,
            )
        ]
        return web.json_response(
            {
                "ok": True,
                "events": events,
                "count": len(events),
            }
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

    app.router.add_post("/v1/agents/register", gateway.register_agent)
    app.router.add_post("/v1/agents/heartbeat", gateway.heartbeat_agent)
    app.router.add_get("/v1/agents", gateway.list_agents)
    app.router.add_get("/v1/control/events", gateway.list_control_events)

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