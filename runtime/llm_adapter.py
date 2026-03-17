from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest


class BaseLLMAdapter(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        prompt: str,
        config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class NoopLLMAdapter(BaseLLMAdapter):
    async def generate(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
        prompt: str,
        config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "provider": "noop",
            "model": (config or {}).get("model", "noop-model"),
            "output_text": prompt,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "metadata": {
                "skill": skill.name,
                "trace_id": context.trace_id,
            },
        }