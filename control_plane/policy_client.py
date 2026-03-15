from __future__ import annotations

from typing import Any, Dict, List, Optional

from control_plane.context import ExecutionContext
from control_plane.decision import PolicyDecision


class PolicyClient:
    """
    PDP Client（冻结接口）

    当前实现：
    - 内置示例策略
    - 支持将来注入 redis / cache / external PDP client
    """

    def __init__(self, redis: Optional[Any] = None):
        self.redis = redis

    async def authorize(self, ctx: ExecutionContext) -> PolicyDecision:
        tenant_id = (ctx.subject or {}).get("tenant_id")
        if not tenant_id:
            return PolicyDecision.deny_decision("TENANT_REQUIRED")

        subject_attr: Dict[str, Any] = (ctx.subject or {}).get("attributes", {}) or {}
        role = subject_attr.get("role") or (ctx.subject or {}).get("role")
        department = subject_attr.get("department") or (ctx.subject or {}).get("department")
        permissions: List[str] = subject_attr.get("permissions") or (ctx.subject or {}).get("permissions") or []

        capabilities: Dict[str, Any] = {
            "allowed_agents": [
                "agent.default",
                "agent.summary",
                "agent.analyze",
                "agent.code",
                "agent.rewrite",
                "agent.translate",
            ],
            "allowed_models": [
                "deepseek-r1-latest",
                "qwen-8b",
            ],
            "allowed_promptflows": ["pf.default"],
            "max_tokens": 4096,
            "memory_access": ["hot", "cold"],
        }

        if role not in ("admin", "owner"):
            capabilities["max_tokens"] = 2048

        if "agent:code" not in permissions and role not in ("admin", "owner"):
            capabilities["allowed_agents"] = [
                a for a in capabilities["allowed_agents"] if a != "agent.code"
            ]

        if department == "sales":
            capabilities["allowed_agents"] = [
                a
                for a in capabilities["allowed_agents"]
                if a in ("agent.default", "agent.summary", "agent.rewrite", "agent.translate")
            ]

        return PolicyDecision.allow_decision(
            capabilities=capabilities,
            metadata={"policy_source": "embedded-demo-policy"},
        )