from __future__ import annotations

from pathlib import Path

from runtime.execution_context import ExecutionContext
from runtime.skill_registry import SkillRegistry
from runtime.skill_resolver import SkillResolver


def test_skill_registry_discovers_bundled_echo_skill() -> None:
    registry = SkillRegistry(
        bundled_dir="skills/bundled",
        local_dir=None,
        workspace_dir=None,
    )

    skills = registry.discover()
    names = [s.name for s in skills]

    assert "echo" in names


def test_skill_registry_get_returns_echo_skill() -> None:
    registry = SkillRegistry(
        bundled_dir="skills/bundled",
        local_dir=None,
        workspace_dir=None,
    )

    skill = registry.get("echo")

    assert skill is not None
    assert skill.name == "echo"
    assert skill.execution.get("type") == "tool"


def test_skill_resolver_resolves_by_required_capability() -> None:
    registry = SkillRegistry(
        bundled_dir="skills/bundled",
        local_dir=None,
        workspace_dir=None,
    )
    resolver = SkillResolver(registry)

    context = ExecutionContext(
        task_id="task-001",
        tenant_id="tenant-a",
        required_capability="echo",
        input_payload={"text": "hello"},
    )

    skill = resolver.resolve(context=context)

    assert skill.name == "echo"
    assert skill.source == "bundled"