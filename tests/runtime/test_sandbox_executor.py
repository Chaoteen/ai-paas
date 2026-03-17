import pytest

from runtime.execution_context import ExecutionContext
from runtime.sandbox_executor import SandboxExecutor
from runtime.skill_manifest import SkillManifest


def build_skill(name: str = "test-skill") -> SkillManifest:
    return SkillManifest(
        name=name,
        version="0.1.0",
        description="test skill",
        source="bundled",
        root_dir="/tmp/test-skill",
        capabilities={},
        execution={"type": "tool"},
        tools=[{"name": "echo"}],
    )


@pytest.mark.asyncio
async def test_sandbox_executor_allows_echo_in_default_mode():
    sandbox = SandboxExecutor()
    context = ExecutionContext(
        task_id="task-001",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
    )
    skill = build_skill()

    async def runner(args):
        return {
            "tool_name": "echo",
            "status": "ok",
            "result": args,
            "metadata": {},
        }

    result = await sandbox.run(
        context=context,
        skill=skill,
        tool_name="echo",
        arguments={"message": "hello"},
        runner=runner,
    )

    assert result["tool_name"] == "echo"
    assert result["metadata"]["sandbox_mode"] == "deny_unsafe"


@pytest.mark.asyncio
async def test_sandbox_executor_blocks_shell_run_in_default_mode():
    sandbox = SandboxExecutor()
    context = ExecutionContext(
        task_id="task-002",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
    )
    skill = build_skill("shell-skill")

    async def runner(args):
        return {
            "tool_name": "shell.run",
            "status": "ok",
            "result": args,
            "metadata": {},
        }

    with pytest.raises(RuntimeError) as exc:
        await sandbox.run(
            context=context,
            skill=skill,
            tool_name="shell.run",
            arguments={"command": "ls"},
            runner=runner,
        )

    assert "blocked by sandbox policy" in str(exc.value)


@pytest.mark.asyncio
async def test_sandbox_executor_inline_mode_allows_shell_run():
    sandbox = SandboxExecutor(sandbox_mode="inline")
    context = ExecutionContext(
        task_id="task-003",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
    )
    skill = build_skill("shell-skill")

    async def runner(args):
        return {
            "tool_name": "shell.run",
            "status": "ok",
            "result": args,
            "metadata": {},
        }

    result = await sandbox.run(
        context=context,
        skill=skill,
        tool_name="shell.run",
        arguments={"command": "ls"},
        runner=runner,
    )

    assert result["tool_name"] == "shell.run"
    assert result["metadata"]["sandbox_mode"] == "inline"