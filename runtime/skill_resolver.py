from __future__ import annotations

from typing import List, Optional

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest
from .skill_registry import SkillRegistry


class SkillResolver:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def resolve(
        self,
        *,
        context: ExecutionContext,
        preferred_skill: Optional[str] = None,
    ) -> SkillManifest:
        skills = self.registry.discover()

        if preferred_skill:
            for skill in skills:
                if skill.name == preferred_skill:
                    return skill
            raise LookupError(f"Preferred skill not found: {preferred_skill}")

        capability = context.required_capability
        matched: List[SkillManifest] = [s for s in skills if s.supports_capability(capability)]

        if not matched:
            raise LookupError(
                f"No skill matched required_capability={capability!r}; available={self.registry.list_names()}"
            )

        matched.sort(key=lambda s: (s.priority, s.name))
        return matched[0]