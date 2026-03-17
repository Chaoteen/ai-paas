from __future__ import annotations

from typing import Any, Dict

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest


class ToolExecutor:
    async def execute(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        tool_name: str,
        arguments: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        args = arguments or {}

        if tool_name == "echo":
            return {
                "tool_name": "echo",
                "status": "ok",
                "result": args,
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
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
                },
            }

        raise RuntimeError(f"Unsupported tool: {tool_name}")