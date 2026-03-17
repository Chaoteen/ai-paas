from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import os

import yaml

from .skill_manifest import SkillManifest


@dataclass(slots=True)
class SkillSource:
    name: str
    path: str
    priority: int


class SkillRegistry:
    """
    优先级越小优先级越高。
    建议默认：
    workspace = 10
    local     = 20
    bundled   = 30
    """

    def __init__(
        self,
        *,
        bundled_dir: str = "skills/bundled",
        local_dir: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        extra_dirs: Optional[List[str]] = None,
    ) -> None:
        self.sources: List[SkillSource] = []
        self._register_source("bundled", bundled_dir, 30)

        if local_dir:
            self._register_source("local", local_dir, 20)
        else:
            home_local = os.path.expanduser("~/.ai-paas/skills")
            self._register_source("local", home_local, 20)

        if workspace_dir:
            self._register_source("workspace", workspace_dir, 10)

        for idx, p in enumerate(extra_dirs or []):
            self._register_source(f"extra-{idx}", p, 50 + idx)

    def _register_source(self, name: str, path: str, priority: int) -> None:
        self.sources.append(SkillSource(name=name, path=path, priority=priority))

    def discover(self) -> List[SkillManifest]:
        found: Dict[str, SkillManifest] = {}
        for source in sorted(self.sources, key=lambda s: s.priority):
            root = Path(source.path)
            if not root.exists() or not root.is_dir():
                continue

            for skill_dir in root.iterdir():
                if not skill_dir.is_dir():
                    continue

                manifest_path = skill_dir / "skill.yaml"
                if not manifest_path.exists():
                    continue

                data = self._load_yaml(manifest_path)
                manifest = SkillManifest.from_dict(
                    data,
                    source=source.name,
                    root_dir=str(skill_dir),
                    priority=source.priority,
                )

                current = found.get(manifest.name)
                if current is None or manifest.priority < current.priority:
                    found[manifest.name] = manifest

        return sorted(found.values(), key=lambda x: (x.priority, x.name))

    def get(self, skill_name: str) -> Optional[SkillManifest]:
        for skill in self.discover():
            if skill.name == skill_name:
                return skill
        return None

    def list_names(self) -> List[str]:
        return [x.name for x in self.discover()]

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid skill manifest: {path}")
        return data