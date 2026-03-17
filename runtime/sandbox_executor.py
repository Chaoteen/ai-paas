from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest


@dataclass(slots=True)
class SandboxDecision:
    allowed: bool
    sandbox_mode: str
    reasons: List[str] = field(default_factory=list)

    @classmethod
    def allow(cls, *, sandbox_mode: str) -> "SandboxDecision":
        return cls(
            allowed=True,
            sandbox_mode=sandbox_mode,
            reasons=[],
        )

    @classmethod
    def deny(cls, *, sandbox_mode: str, reasons: List[str]) -> "SandboxDecision":
        return cls(
            allowed=False,
            sandbox_mode=sandbox_mode,
            reasons=reasons,
        )


class SandboxExecutor:
    """
    Phase 12-C:
    先建立 sandbox 抽象层，不做真实 OS 隔离。
    当前支持两种模式：
    - inline: 允许执行
    - deny_unsafe: 拒绝高风险 tool
    """

    UNSAFE_TOOLS = {
        "shell.run",
        "fs.write",
        "secrets.get",
    }

    def __init__(self, *, sandbox_mode: str = "deny_unsafe") -> None:
        self.sandbox_mode = sandbox_mode

    def evaluate(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        tool_name: str,
    ) -> SandboxDecision:
        if self.sandbox_mode == "inline":
            return SandboxDecision.allow(sandbox_mode="inline")

        if self.sandbox_mode == "deny_unsafe":
            if tool_name in self.UNSAFE_TOOLS:
                return SandboxDecision.deny(
                    sandbox_mode="deny_unsafe",
                    reasons=[
                        (
                            f"Tool '{tool_name}' is blocked by sandbox policy "
                            f"mode={self.sandbox_mode}"
                        )
                    ],
                )
            return SandboxDecision.allow(sandbox_mode="deny_unsafe")

        return SandboxDecision.deny(
            sandbox_mode=self.sandbox_mode,
            reasons=[f"Unknown sandbox mode: {self.sandbox_mode}"],
        )

    async def run(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        tool_name: str,
        arguments: Dict[str, Any],
        runner: Callable[[Dict[str, Any]], Any],
    ) -> Dict[str, Any]:
        decision = self.evaluate(
            context=context,
            skill=skill,
            tool_name=tool_name,
        )
        if not decision.allowed:
            raise RuntimeError("; ".join(decision.reasons))

        result = await runner(arguments)

        if not isinstance(result, dict):
            raise RuntimeError("Sandbox runner must return dict result")

        metadata = dict(result.get("metadata", {}) or {})
        metadata["sandbox_mode"] = decision.sandbox_mode
        result["metadata"] = metadata
        return result