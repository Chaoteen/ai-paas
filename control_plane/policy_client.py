# ai-os/control_plane/policy_client.py

from __future__ import annotations

from typing import Any, Dict, Optional, List

from control_plane.context import ExecutionContext
from control_plane.decision import PolicyDecision


class PolicyClient:
    """
    PDP Client（冻结接口）
    - 输入：ExecutionContext
    - 输出：PolicyDecision

    当前实现：内置示例策略（可替换为外部 PDP）
    """

    def __init__(self):
        # 预留：remote PDP endpoint / auth / cache / audit sink 等
        pass

    async def authorize(self, ctx: ExecutionContext) -> PolicyDecision:
        """
        冻结授权接口：PEP -> PDP

        注意：
        - tenant_id 从 ctx.subject.tenant_id 获取
        - ABAC 要素来自 ctx.subject / ctx.action / ctx.resource / ctx.environment
        """
        tenant_id = (ctx.subject or {}).get("tenant_id")
        if not tenant_id:
            return PolicyDecision(
                allow=False,
                reason="TENANT_REQUIRED",
                capabilities={},
            )

        # ===== 内置示例策略（可替换为外部 PDP）=====
        # 你可以基于：
        # - ctx.subject["attributes"] (如角色/部门/权限/等级)
        # - ctx.resource["attributes"] (资源敏感级别、owner、标签)
        # - ctx.environment (区域、合规标签、来源、时间窗)
        # - ctx.action (prompt.execute / model.infer / promptflow.run ...)
        subject_attr: Dict[str, Any] = (ctx.subject or {}).get("attributes", {}) or {}
        role = subject_attr.get("role") or (ctx.subject or {}).get("role")
        department = subject_attr.get("department") or (ctx.subject or {}).get("department")
        permissions: List[str] = subject_attr.get("permissions") or (ctx.subject or {}).get("permissions") or []

        # 示例：默认能力（最小可用集）
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

        # 示例：基于角色/权限的差异化
        # - 非管理员降 token 上限
        if role not in ("admin", "owner"):
            capabilities["max_tokens"] = 2048

        # - 没有 code 权限则禁用 agent.code
        if "agent:code" not in permissions and role not in ("admin", "owner"):
            capabilities["allowed_agents"] = [a for a in capabilities["allowed_agents"] if a != "agent.code"]

        # 示例：部门策略（可选）
        if department == "sales":
            # 销售默认更偏 summary/rewrite
            capabilities["allowed_agents"] = [
                a for a in capabilities["allowed_agents"]
                if a in ("agent.default", "agent.summary", "agent.rewrite", "agent.translate")
            ]

        # 这里也可以做资源级别控制，例如：
        # resource_level = (ctx.resource or {}).get("attributes", {}).get("sensitivity", "normal")
        # if resource_level == "high" and role not in ("admin",):
        #     return PolicyDecision(allow=False, reason="RESOURCE_SENSITIVITY_RESTRICTED", capabilities={})

        return PolicyDecision(
            allow=True,
            reason=None,
            capabilities=capabilities,
        )
