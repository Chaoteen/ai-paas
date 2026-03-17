from __future__ import annotations

from typing import Any, Dict

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest
from .tool_capability_guard import ToolCapabilityDecision, ToolCapabilityGuard


class ToolExecutor:
    def __init__(
        self,
        *,
        capability_guard: ToolCapabilityGuard | None = None,
    ) -> None:
        self.capability_guard = capability_guard or ToolCapabilityGuard()

    async def execute(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        tool_name: str,
        arguments: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        args = arguments or {}

        decision = self.capability_guard.evaluate(
            tool_name=tool_name,
            allowed_capabilities=context.allowed_capabilities,
        )
        if not decision.allowed:
            raise RuntimeError("; ".join(decision.reasons))

        if tool_name == "echo":
            return {
                "tool_name": "echo",
                "status": "ok",
                "result": args,
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
                    "granted_capabilities": decision.granted_capabilities,
                },
            }

        if tool_name == "template.render":
            template = str(args.get("template", ""))
            variables = dict(args.get("variables", {}) or {})
            try:
                rendered = template.format(**variables)
            except Exception as exc:
                raise RuntimeError(f"template.render failed: {exc}") from exc

            return {
                "tool_name": "template.render",
                "status": "ok",
                "result": {"rendered": rendered},
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
                    "granted_capabilities": decision.granted_capabilities,
                },
            }

        if tool_name == "http.fetch":
            # Phase 12-B 先不做真实网络请求，只验证 capability enforcement
            return {
                "tool_name": "http.fetch",
                "status": "ok",
                "result": {
                    "url": args.get("url"),
                    "note": "network tool placeholder",
                },
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
                    "granted_capabilities": decision.granted_capabilities,
                },
            }

        raise RuntimeError(f"Unsupported tool: {tool_name}")