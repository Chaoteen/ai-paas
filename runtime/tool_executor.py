from __future__ import annotations

from typing import Any, Dict

from .execution_context import ExecutionContext
from .sandbox_executor import SandboxExecutor
from .skill_manifest import SkillManifest
from .tool_capability_guard import ToolCapabilityGuard


class ToolExecutor:
    def __init__(
        self,
        *,
        capability_guard: ToolCapabilityGuard | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        self.capability_guard = capability_guard or ToolCapabilityGuard()
        self.sandbox_executor = sandbox_executor or SandboxExecutor()

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

        async def _runner(resolved_args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._execute_impl(
                context=context,
                skill=skill,
                tool_name=tool_name,
                arguments=resolved_args,
                granted_capabilities=decision.granted_capabilities,
            )

        return await self.sandbox_executor.run(
            context=context,
            skill=skill,
            tool_name=tool_name,
            arguments=args,
            runner=_runner,
        )

    async def _execute_impl(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        tool_name: str,
        arguments: Dict[str, Any],
        granted_capabilities: list[str],
    ) -> Dict[str, Any]:
        if tool_name == "echo":
            return {
                "tool_name": "echo",
                "status": "ok",
                "result": arguments,
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
                    "granted_capabilities": granted_capabilities,
                },
            }

        if tool_name == "template.render":
            template = str(arguments.get("template", ""))
            variables = dict(arguments.get("variables", {}) or {})
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
                    "granted_capabilities": granted_capabilities,
                },
            }

        if tool_name == "http.fetch":
            return {
                "tool_name": "http.fetch",
                "status": "ok",
                "result": {
                    "url": arguments.get("url"),
                    "note": "network tool placeholder",
                },
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
                    "granted_capabilities": granted_capabilities,
                },
            }

        if tool_name == "shell.run":
            return {
                "tool_name": "shell.run",
                "status": "ok",
                "result": {
                    "command": arguments.get("command"),
                    "note": "shell tool placeholder",
                },
                "metadata": {
                    "trace_id": context.trace_id,
                    "skill": skill.name,
                    "granted_capabilities": granted_capabilities,
                },
            }

        raise RuntimeError(f"Unsupported tool: {tool_name}")