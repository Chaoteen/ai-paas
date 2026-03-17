from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(slots=True)
class SkillManifest:
    name: str
    version: str
    description: str
    source: str
    root_dir: str
    use_cases: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    capabilities: Dict[str, bool] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    llm: Dict[str, Any] = field(default_factory=dict)
    tools: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 100

    @property
    def root_path(self) -> Path:
        return Path(self.root_dir)

    @property
    def manifest_path(self) -> Path:
        return self.root_path / "skill.yaml"

    @property
    def markdown_path(self) -> Path:
        return self.root_path / "SKILL.md"

    def supports_capability(self, capability: str | None) -> bool:
        if not capability:
            return True
        if capability == self.name:
            return True
        if capability in self.triggers:
            return True
        return capability in self.use_cases

    def requested_capabilities(self) -> List[str]:
        return [k for k, v in self.capabilities.items() if v]

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        source: str,
        root_dir: str,
        priority: int,
    ) -> "SkillManifest":
        return cls(
            name=str(data["name"]),
            version=str(data.get("version", "0.1.0")),
            description=str(data.get("description", "")),
            source=source,
            root_dir=root_dir,
            use_cases=list(data.get("use_cases", []) or []),
            triggers=list(data.get("triggers", []) or []),
            capabilities=dict(data.get("capabilities", {}) or {}),
            inputs=dict(data.get("inputs", {}) or {}),
            outputs=dict(data.get("outputs", {}) or {}),
            execution=dict(data.get("execution", {}) or {}),
            llm=dict(data.get("llm", {}) or {}),
            tools=list(data.get("tools", []) or []),
            priority=priority,
        )