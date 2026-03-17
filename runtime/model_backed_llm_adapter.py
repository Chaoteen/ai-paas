from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtime.execution_context import ExecutionContext
from runtime.llm_adapter import BaseLLMAdapter
from runtime.model_service import ModelInvocationContext, ModelService
from runtime.skill_manifest import SkillManifest
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelProvider,
    ModelRequest,
    ToolSpec,
)


class ModelBackedLLMAdapter(BaseLLMAdapter):
    """
    Bridge adapter:
    keeps the existing Runtime LLM contract unchanged, but routes execution
    into the new Phase 14 model layer.
    """

    def __init__(
        self,
        *,
        model_service: ModelService,
        default_model_ref: Optional[str] = None,
    ) -> None:
        self.model_service = model_service
        self.default_model_ref = default_model_ref

    async def generate(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        prompt: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        request = self._build_model_request(prompt=prompt, skill=skill, config=config)
        invocation_context = self._build_invocation_context(
            context=context,
            skill=skill,
            config=config,
            request=request,
        )
        response = await self.model_service.generate(
            request=request,
            context=invocation_context,
        )

        return {
            "provider": response.provider.value,
            "model": response.model_name,
            "content": response.message.content,
            "finish_reason": response.finish_reason,
            "tool_calls": [
                {
                    "id": item.id,
                    "name": item.name,
                    "arguments_json": item.arguments_json,
                }
                for item in response.message.tool_calls
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "latency_ms": response.latency_ms,
        }

    def _build_model_request(
        self,
        *,
        prompt: str,
        skill: SkillManifest,
        config: Dict[str, Any],
    ) -> ModelRequest:
        temperature = config.get("temperature")
        max_tokens = config.get("max_tokens")
        top_p = config.get("top_p")
        stream = bool(config.get("stream", False))
        response_format = config.get("response_format")

        tools = self._build_tools(skill=skill)

        return ModelRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content=prompt,
                )
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            response_format=response_format,
            tools=tools,
            metadata={
                "skill_name": skill.name,
                "skill_source": skill.source,
                "skill_version": skill.version,
            },
        )

    def _build_invocation_context(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        config: Dict[str, Any],
        request: ModelRequest,
    ) -> ModelInvocationContext:
        provider = self._parse_provider(config.get("provider"))
        model_ref = self._resolve_model_ref(config=config)
        routing_policy = self._resolve_routing_policy(config=config)

        requires = {ModelCapability.CHAT}
        if request.tools:
            requires.add(ModelCapability.TOOLS)
        if request.stream:
            requires.add(ModelCapability.STREAMING)
        if request.response_format:
            requires.add(ModelCapability.JSON_MODE)

        merged_metadata = {
            "skill_name": skill.name,
            "skill_source": skill.source,
            "skill_version": skill.version,
            **dict(context.metadata),
        }

        return ModelInvocationContext.from_execution_context(
            context,
            model_ref=model_ref,
            provider=provider,
            requires=frozenset(requires),
            routing_policy=routing_policy,
            metadata=merged_metadata,
        )

    def _resolve_model_ref(self, *, config: Dict[str, Any]) -> Optional[str]:
        model_ref = config.get("model_ref")
        if isinstance(model_ref, str) and model_ref.strip():
            return model_ref.strip()

        alias = config.get("alias")
        if isinstance(alias, str) and alias.strip():
            return alias.strip()

        provider = config.get("provider")
        model = config.get("model")
        if isinstance(provider, str) and provider.strip() and isinstance(model, str) and model.strip():
            return f"{provider.strip().lower()}:{model.strip()}"

        return self.default_model_ref

    def _resolve_routing_policy(self, *, config: Dict[str, Any]) -> Optional[str]:
        value = config.get("routing_policy")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        return None

    def _parse_provider(self, value: Any) -> Optional[ModelProvider]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return ModelProvider(value.strip().lower())
        except ValueError:
            return None

    def _build_tools(self, *, skill: SkillManifest) -> List[ToolSpec]:
        tools: List[ToolSpec] = []
        for item in skill.tools:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            description = str(item.get("description", f"Tool: {name}"))
            parameters = item.get("parameters")
            if not isinstance(parameters, dict):
                parameters = {
                    "type": "object",
                    "properties": {},
                }
            tools.append(
                ToolSpec(
                    name=name,
                    description=description,
                    parameters=parameters,
                )
            )
        return tools