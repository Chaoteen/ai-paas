from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .capability_guard import CapabilityGuard, CapabilityGuardDecision
from .execution_context import ExecutionContext
from .llm_adapter import BaseLLMAdapter, NoopLLMAdapter
from .policy_engine import PolicyDecision, PolicyEngine
from .skill_manifest import SkillManifest
from .skill_registry import SkillRegistry
from .skill_resolver import SkillResolver
from .tool_executor import ToolExecutor


@dataclass(slots=True)
class AgentRuntimeResult:
    status: str
    skill_name: Optional[str] = None
    skill_source: Optional[str] = None
    granted_capabilities: list[str] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "skill_name": self.skill_name,
            "skill_source": self.skill_source,
            "granted_capabilities": list(self.granted_capabilities),
            "output": dict(self.output),
            "error": self.error,
        }


class AgentRuntime:
    def __init__(
        self,
        *,
        registry: SkillRegistry,
        resolver: SkillResolver,
        policy_engine: PolicyEngine,
        capability_guard: CapabilityGuard | None = None,
        llm_adapter: BaseLLMAdapter | None = None,
        tool_executor: ToolExecutor | None = None,
        data_bus: Any | None = None,
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.policy_engine = policy_engine
        self.capability_guard = capability_guard or CapabilityGuard()
        self.llm_adapter = llm_adapter or NoopLLMAdapter()
        self.tool_executor = tool_executor or ToolExecutor()
        self.data_bus = data_bus

    async def execute(
        self,
        *,
        context: ExecutionContext,
        preferred_skill: str | None = None,
    ) -> AgentRuntimeResult:
        try:
            skill = self.resolver.resolve(context=context, preferred_skill=preferred_skill)
            await self._publish(
                event_type="skill.selected",
                context=context,
                payload={
                    "skill_name": skill.name,
                    "skill_source": skill.source,
                    "skill_version": skill.version,
                },
            )

            capability_decision = self.capability_guard.evaluate(
                context=context,
                skill=skill,
            )
            if not capability_decision.allowed:
                await self._publish(
                    event_type="security.denied",
                    context=context,
                    payload={
                        "skill_name": skill.name,
                        "reasons": capability_decision.reasons,
                        "required_capabilities": capability_decision.required_capabilities,
                        "denied_capabilities": capability_decision.denied_capabilities,
                    },
                )
                return AgentRuntimeResult(
                    status="failed",
                    skill_name=skill.name,
                    skill_source=skill.source,
                    error="; ".join(capability_decision.reasons),
                )

            decision = self.policy_engine.evaluate(context=context, skill=skill)
            if not decision.allowed:
                await self._publish(
                    event_type="security.denied",
                    context=context,
                    payload={
                        "skill_name": skill.name,
                        "reasons": decision.reasons,
                    },
                )
                return AgentRuntimeResult(
                    status="failed",
                    skill_name=skill.name,
                    skill_source=skill.source,
                    error="; ".join(decision.reasons),
                )

            execution_type = str(skill.execution.get("type", "llm")).strip().lower()

            if execution_type == "tool":
                result = await self._execute_tool(
                    context=context,
                    skill=skill,
                    granted=decision,
                )
            else:
                result = await self._execute_llm(
                    context=context,
                    skill=skill,
                    granted=decision,
                )

            granted_caps = sorted(
                set(capability_decision.granted_capabilities) | set(decision.granted_capabilities)
            )

            return AgentRuntimeResult(
                status="completed",
                skill_name=skill.name,
                skill_source=skill.source,
                granted_capabilities=granted_caps,
                output=result,
            )
        except Exception as exc:
            return AgentRuntimeResult(
                status="failed",
                error=str(exc),
            )

    async def _execute_llm(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        granted: PolicyDecision,
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(context=context, skill=skill)

        await self._publish(
            event_type="llm.invoking",
            context=context,
            payload={
                "skill_name": skill.name,
                "provider": skill.llm.get("provider", "noop"),
                "model": skill.llm.get("model", "noop-model"),
            },
        )

        result = await self.llm_adapter.generate(
            context=context,
            skill=skill,
            prompt=prompt,
            config=skill.llm,
        )

        await self._publish(
            event_type="llm.completed",
            context=context,
            payload={
                "skill_name": skill.name,
                "provider": result.get("provider"),
                "model": result.get("model"),
            },
        )

        return {
            "mode": "llm",
            "prompt": prompt,
            "llm_result": result,
            "granted_capabilities": granted.granted_capabilities,
        }

    async def _execute_tool(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        granted: PolicyDecision,
    ) -> Dict[str, Any]:
        tool_cfg = skill.tools[0] if skill.tools else {"name": "echo"}
        tool_name = str(tool_cfg.get("name", "echo"))
        args = self._build_tool_arguments(context=context, skill=skill)

        await self._publish(
            event_type="tool.invoking",
            context=context,
            payload={
                "skill_name": skill.name,
                "tool_name": tool_name,
            },
        )

        tool_result = await self.tool_executor.execute(
            context=context,
            skill=skill,
            tool_name=tool_name,
            arguments=args,
        )

        await self._publish(
            event_type="tool.completed",
            context=context,
            payload={
                "skill_name": skill.name,
                "tool_name": tool_name,
            },
        )

        return {
            "mode": "tool",
            "tool_result": tool_result,
            "granted_capabilities": granted.granted_capabilities,
        }

    def _build_prompt(self, *, context: ExecutionContext, skill: SkillManifest) -> str:
        input_text = context.input_payload.get("text")
        if input_text is None:
            input_text = context.input_payload.get("input")
        if input_text is None:
            input_text = str(context.input_payload)

        system_hint = skill.description or f"Execute skill: {skill.name}"
        return f"{system_hint}\n\nINPUT:\n{input_text}"

    def _build_tool_arguments(self, *, context: ExecutionContext, skill: SkillManifest) -> Dict[str, Any]:
        return {
            "task_id": context.task_id,
            "tenant_id": context.tenant_id,
            "input": dict(context.input_payload),
            "metadata": dict(context.metadata),
            "skill_name": skill.name,
        }

    async def _publish(self, *, event_type: str, context: ExecutionContext, payload: Dict[str, Any]) -> None:
        if self.data_bus is None:
            return

        await self.data_bus.publish(
            event_type=event_type,
            payload=payload,
            source="runtime.agent_runtime",
            tenant_id=context.tenant_id,
            correlation_id=context.correlation_id,
            task_id=context.task_id,
            workflow_id=context.workflow_id,
        )