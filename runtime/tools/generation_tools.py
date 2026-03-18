from __future__ import annotations

from typing import Any, Dict, Optional

from runtime.execution_context import ExecutionContext
from runtime.generation.types import (
    GenerationCapability,
    GenerationProvider,
    GenerationRequest,
    GenerationTaskType,
)
from runtime.generation_service import GenerationInvocationContext, GenerationService
from runtime.skill_manifest import SkillManifest


class GenerationToolSet:
    def __init__(
        self,
        *,
        generation_service: GenerationService,
        default_image_model_ref: Optional[str] = None,
        default_video_model_ref: Optional[str] = None,
    ) -> None:
        self.generation_service = generation_service
        self.default_image_model_ref = default_image_model_ref
        self.default_video_model_ref = default_video_model_ref

    async def execute(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        tool_name: str,
        arguments: Dict[str, Any],
        granted_capabilities: list[str],
    ) -> Dict[str, Any]:
        if tool_name == "generation.image":
            return await self._generate_image(
                context=context,
                skill=skill,
                arguments=arguments,
                granted_capabilities=granted_capabilities,
            )

        if tool_name == "generation.video":
            return await self._generate_video(
                context=context,
                skill=skill,
                arguments=arguments,
                granted_capabilities=granted_capabilities,
            )

        raise RuntimeError(f"Unsupported generation tool: {tool_name}")

    async def _generate_image(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        arguments: Dict[str, Any],
        granted_capabilities: list[str],
    ) -> Dict[str, Any]:
        tool_cfg = self._resolve_tool_cfg(skill=skill, tool_name="generation.image")
        prompt = self._resolve_prompt(arguments=arguments, tool_cfg=tool_cfg)
        request = GenerationRequest(
            task_type=GenerationTaskType.IMAGE,
            prompt=prompt,
            negative_prompt=self._pick(arguments, tool_cfg, "negative_prompt"),
            width=self._pick_int(arguments, tool_cfg, "width"),
            height=self._pick_int(arguments, tool_cfg, "height"),
            seed=self._pick_int(arguments, tool_cfg, "seed"),
            count=self._pick_int(arguments, tool_cfg, "count", default=1) or 1,
            metadata={
                "skill_name": skill.name,
                "skill_source": skill.source,
                "skill_version": skill.version,
            },
        )

        invocation = GenerationInvocationContext.from_execution_context(
            context,
            model_ref=self._resolve_model_ref(arguments=arguments, tool_cfg=tool_cfg, task_type=GenerationTaskType.IMAGE),
            provider=self._resolve_provider(arguments=arguments, tool_cfg=tool_cfg),
            requires=frozenset({GenerationCapability.IMAGE}),
            routing_policy=self._resolve_routing_policy(arguments=arguments, tool_cfg=tool_cfg, default="image_first"),
            metadata={"tool_name": "generation.image", "skill_name": skill.name},
        )

        response = await self.generation_service.generate(
            request=request,
            context=invocation,
        )

        return self._to_tool_result(
            tool_name="generation.image",
            context=context,
            skill=skill,
            granted_capabilities=granted_capabilities,
            response=response,
        )

    async def _generate_video(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        arguments: Dict[str, Any],
        granted_capabilities: list[str],
    ) -> Dict[str, Any]:
        tool_cfg = self._resolve_tool_cfg(skill=skill, tool_name="generation.video")
        prompt = self._resolve_prompt(arguments=arguments, tool_cfg=tool_cfg)
        request = GenerationRequest(
            task_type=GenerationTaskType.VIDEO,
            prompt=prompt,
            negative_prompt=self._pick(arguments, tool_cfg, "negative_prompt"),
            width=self._pick_int(arguments, tool_cfg, "width"),
            height=self._pick_int(arguments, tool_cfg, "height"),
            duration_seconds=self._pick_int(arguments, tool_cfg, "duration_seconds"),
            fps=self._pick_int(arguments, tool_cfg, "fps"),
            seed=self._pick_int(arguments, tool_cfg, "seed"),
            count=self._pick_int(arguments, tool_cfg, "count", default=1) or 1,
            metadata={
                "skill_name": skill.name,
                "skill_source": skill.source,
                "skill_version": skill.version,
            },
        )

        invocation = GenerationInvocationContext.from_execution_context(
            context,
            model_ref=self._resolve_model_ref(arguments=arguments, tool_cfg=tool_cfg, task_type=GenerationTaskType.VIDEO),
            provider=self._resolve_provider(arguments=arguments, tool_cfg=tool_cfg),
            requires=frozenset({GenerationCapability.VIDEO}),
            routing_policy=self._resolve_routing_policy(arguments=arguments, tool_cfg=tool_cfg, default="video_first"),
            metadata={"tool_name": "generation.video", "skill_name": skill.name},
        )

        response = await self.generation_service.generate(
            request=request,
            context=invocation,
        )

        return self._to_tool_result(
            tool_name="generation.video",
            context=context,
            skill=skill,
            granted_capabilities=granted_capabilities,
            response=response,
        )

    def _resolve_tool_cfg(self, *, skill: SkillManifest, tool_name: str) -> Dict[str, Any]:
        for item in skill.tools:
            if str(item.get("name", "")).strip() == tool_name:
                return dict(item)
        return {}

    def _resolve_prompt(self, *, arguments: Dict[str, Any], tool_cfg: Dict[str, Any]) -> str:
        if "prompt" in arguments and arguments["prompt"]:
            return str(arguments["prompt"])

        input_payload = dict(arguments.get("input", {}) or {})
        if input_payload.get("prompt"):
            return str(input_payload["prompt"])
        if input_payload.get("text"):
            return str(input_payload["text"])

        if tool_cfg.get("prompt"):
            return str(tool_cfg["prompt"])

        raise RuntimeError("generation tool requires prompt")

    def _resolve_model_ref(
        self,
        *,
        arguments: Dict[str, Any],
        tool_cfg: Dict[str, Any],
        task_type: GenerationTaskType,
    ) -> Optional[str]:
        if isinstance(arguments.get("model_ref"), str) and arguments["model_ref"].strip():
            return arguments["model_ref"].strip()
        if isinstance(tool_cfg.get("model_ref"), str) and tool_cfg["model_ref"].strip():
            return tool_cfg["model_ref"].strip()

        provider = arguments.get("provider") or tool_cfg.get("provider")
        model = arguments.get("model") or tool_cfg.get("model")
        if isinstance(provider, str) and provider.strip() and isinstance(model, str) and model.strip():
            return f"{provider.strip().lower()}:{model.strip()}"

        if task_type == GenerationTaskType.IMAGE:
            return self.default_image_model_ref
        return self.default_video_model_ref

    def _resolve_provider(
        self,
        *,
        arguments: Dict[str, Any],
        tool_cfg: Dict[str, Any],
    ) -> Optional[GenerationProvider]:
        value = arguments.get("provider") or tool_cfg.get("provider")
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return GenerationProvider(value.strip().lower())
        except ValueError:
            return None

    def _resolve_routing_policy(
        self,
        *,
        arguments: Dict[str, Any],
        tool_cfg: Dict[str, Any],
        default: str,
    ) -> str:
        value = arguments.get("routing_policy") or tool_cfg.get("routing_policy") or default
        return str(value).strip().lower()

    def _pick(self, arguments: Dict[str, Any], tool_cfg: Dict[str, Any], key: str) -> Any:
        if key in arguments and arguments[key] is not None:
            return arguments[key]
        input_payload = dict(arguments.get("input", {}) or {})
        if key in input_payload and input_payload[key] is not None:
            return input_payload[key]
        return tool_cfg.get(key)

    def _pick_int(
        self,
        arguments: Dict[str, Any],
        tool_cfg: Dict[str, Any],
        key: str,
        default: Optional[int] = None,
    ) -> Optional[int]:
        value = self._pick(arguments, tool_cfg, key)
        if value is None:
            return default
        return int(value)

    def _to_tool_result(
        self,
        *,
        tool_name: str,
        context: ExecutionContext,
        skill: SkillManifest,
        granted_capabilities: list[str],
        response,
    ) -> Dict[str, Any]:
        return {
            "tool_name": tool_name,
            "status": "ok",
            "result": {
                "provider": response.provider.value,
                "model_name": response.model_name,
                "task_type": response.task_type.value,
                "artifacts": [
                    {
                        "uri": item.uri,
                        "mime_type": item.mime_type,
                        "metadata": dict(item.metadata),
                    }
                    for item in response.artifacts
                ],
            },
            "metadata": {
                "trace_id": context.trace_id,
                "skill": skill.name,
                "granted_capabilities": granted_capabilities,
            },
        }