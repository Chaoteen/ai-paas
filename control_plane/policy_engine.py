# policy_engine.py
# ============================================================
# Control Plane – ABAC Policy Engine (Production-Grade)
# 支持多租户 / 多主体 / 多资源 / 多动作 / 冻结态 / 配额 / 上下文感知
# ============================================================

import time
import uuid
from typing import Dict, Any, List, Optional


# ============================================================
# Policy Decision
# ============================================================

class PolicyDecision:
    def __init__(self, allow: bool, reason: str = "", obligations: Optional[Dict[str, Any]] = None):
        self.allow = allow
        self.reason = reason
        self.obligations = obligations or {}

    def to_dict(self):
        return {
            "allow": self.allow,
            "reason": self.reason,
            "obligations": self.obligations
        }


# ============================================================
# Policy Context
# ============================================================

class PolicyContext:
    """
    统一的 ABAC 上下文
    """

    def __init__(
        self,
        tenant: Dict[str, Any],
        subject: Dict[str, Any],
        resource: Dict[str, Any],
        action: str,
        environment: Optional[Dict[str, Any]] = None
    ):
        self.tenant = tenant
        self.subject = subject
        self.resource = resource
        self.action = action
        self.environment = environment or {}
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "tenant": self.tenant,
            "subject": self.subject,
            "resource": self.resource,
            "action": self.action,
            "environment": self.environment,
            "timestamp": self.timestamp
        }


# ============================================================
# Policy Rule
# ============================================================

class PolicyRule:
    """
    单条 ABAC 规则
    """

    def __init__(
        self,
        rule_id: str,
        effect: str,  # "allow" | "deny"
        conditions: Dict[str, Any],
        obligations: Optional[Dict[str, Any]] = None,
        priority: int = 100
    ):
        self.rule_id = rule_id
        self.effect = effect
        self.conditions = conditions
        self.obligations = obligations or {}
        self.priority = priority

    def match(self, ctx: PolicyContext) -> bool:
        """
        条件匹配（严格 AND）
        """
        data = ctx.to_dict()

        for path, expected in self.conditions.items():
            value = self._resolve_path(data, path)
            if value != expected:
                return False
        return True

    @staticmethod
    def _resolve_path(data: Dict[str, Any], path: str):
        parts = path.split(".")
        cur = data
        for p in parts:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur


# ============================================================
# Policy Set
# ============================================================

class PolicySet:
    """
    一个租户的完整策略集
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.rules: List[PolicyRule] = []
        self.frozen = False
        self.freeze_reason = None
        self.freeze_version = None

    def add_rule(self, rule: PolicyRule):
        if self.frozen:
            raise RuntimeError("PolicySet is frozen, cannot modify")
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def freeze(self, reason: str):
        self.frozen = True
        self.freeze_reason = reason
        self.freeze_version = f"freeze-{uuid.uuid4().hex[:8]}"

    def unfreeze(self):
        self.frozen = False
        self.freeze_reason = None
        self.freeze_version = None


# ============================================================
# Policy Engine (核心)
# ============================================================

class PolicyEngine:
    """
    Control Plane 中央 Policy Engine
    """

    def __init__(self):
        self.policy_sets: Dict[str, PolicySet] = {}
        self.audit_log: List[Dict[str, Any]] = []

    # -----------------------------
    # PolicySet 管理
    # -----------------------------

    def get_or_create_policy_set(self, tenant_id: str) -> PolicySet:
        if tenant_id not in self.policy_sets:
            self.policy_sets[tenant_id] = PolicySet(tenant_id)
        return self.policy_sets[tenant_id]

    def freeze_tenant_policy(self, tenant_id: str, reason: str):
        ps = self.get_or_create_policy_set(tenant_id)
        ps.freeze(reason)

    # -----------------------------
    # 决策入口
    # -----------------------------

    def evaluate(self, ctx: PolicyContext) -> PolicyDecision:
        tenant_id = ctx.tenant.get("tenant_id")
        ps = self.policy_sets.get(tenant_id)

        # 没有策略 = 默认拒绝
        if not ps:
            decision = PolicyDecision(False, "NO_POLICY_SET")
            self._audit(ctx, decision)
            return decision

        # 冻结态：只能执行 allow_readonly 动作
        if ps.frozen:
            if ctx.action not in ("read", "list", "observe"):
                decision = PolicyDecision(
                    False,
                    "TENANT_POLICY_FROZEN",
                    {"freeze_version": ps.freeze_version}
                )
                self._audit(ctx, decision)
                return decision

        # 按优先级评估
        for rule in ps.rules:
            if rule.match(ctx):
                decision = PolicyDecision(
                    allow=(rule.effect == "allow"),
                    reason=f"RULE:{rule.rule_id}",
                    obligations=rule.obligations
                )
                self._audit(ctx, decision)
                return decision

        # 默认拒绝
        decision = PolicyDecision(False, "DEFAULT_DENY")
        self._audit(ctx, decision)
        return decision

    # -----------------------------
    # 审计
    # -----------------------------

    def _audit(self, ctx: PolicyContext, decision: PolicyDecision):
        self.audit_log.append({
            "time": time.time(),
            "context": ctx.to_dict(),
            "decision": decision.to_dict()
        })

    def get_audit_log(self, limit: int = 100):
        return self.audit_log[-limit:]


# ============================================================
# 内置默认策略（生产可用）
# ============================================================

def load_default_policies(engine: PolicyEngine):
    """
    默认平台级策略（你可以直接用）
    """
    ps = engine.get_or_create_policy_set("platform")

    # 超级管理员
    ps.add_rule(
        PolicyRule(
            rule_id="platform-admin-all",
            effect="allow",
            priority=1,
            conditions={
                "subject.role": "platform_admin"
            }
        )
    )

    # Tenant Admin 可管理自身资源
    ps.add_rule(
        PolicyRule(
            rule_id="tenant-admin-manage",
            effect="allow",
            priority=10,
            conditions={
                "subject.role": "tenant_admin",
                "tenant.tenant_id": "tenant_id"  # 逻辑占位，运行时做替换
            }
        )
    )

    # 普通用户只能执行 inference
    ps.add_rule(
        PolicyRule(
            rule_id="user-inference-only",
            effect="allow",
            priority=50,
            conditions={
                "subject.role": "user",
                "action": "inference"
            }
        )
    )

    # 明确拒绝跨租户
    ps.add_rule(
        PolicyRule(
            rule_id="deny-cross-tenant",
            effect="deny",
            priority=5,
            conditions={
                "tenant.cross": True
            }
        )
    )


# ============================================================
# 单例
# ============================================================

GLOBAL_POLICY_ENGINE = PolicyEngine()
load_default_policies(GLOBAL_POLICY_ENGINE)
