import pytest

from runtime.execution_context import ExecutionContext
from runtime.sandbox_executor import SandboxExecutor
from runtime.skill_manifest import SkillManifest
from runtime.tool_executor import ToolExecutor


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
async def test_tool_executor_allows_echo_without_capability():
    executor = ToolExecutor()
    context = ExecutionContext(
        task_id="task-001",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
        allowed_capabilities=[],
    )
    skill = build_skill()

    result = await executor.execute(
        context=context,
        skill=skill,
        tool_name="echo",
        arguments={"message": "hello"},
    )

    assert result["tool_name"] == "echo"
    assert result["status"] == "ok"
    assert result["metadata"]["sandbox_mode"] == "deny_unsafe"


@pytest.mark.asyncio
async def test_tool_executor_denies_http_fetch_without_network():
    executor = ToolExecutor()
    context = ExecutionContext(
        task_id="task-002",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
        allowed_capabilities=[],
    )
    skill = build_skill("network-skill")

    with pytest.raises(RuntimeError) as exc:
        await executor.execute(
            context=context,
            skill=skill,
            tool_name="http.fetch",
            arguments={"url": "https://example.com"},
        )

    assert "Tool 'http.fetch' requires capabilities network" in str(exc.value)


@pytest.mark.asyncio
async def test_tool_executor_allows_http_fetch_with_network():
    executor = ToolExecutor()
    context = ExecutionContext(
        task_id="task-003",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
        allowed_capabilities=["network"],
    )
    skill = build_skill("network-skill")

    result = await executor.execute(
        context=context,
        skill=skill,
        tool_name="http.fetch",
        arguments={"url": "https://example.com"},
    )

    assert result["tool_name"] == "http.fetch"
    assert result["status"] == "ok"
    assert result["result"]["url"] == "https://example.com"
    assert result["metadata"]["sandbox_mode"] == "deny_unsafe"


@pytest.mark.asyncio
async def test_tool_executor_blocks_shell_run_in_default_sandbox():
    executor = ToolExecutor()
    context = ExecutionContext(
        task_id="task-004",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
        allowed_capabilities=["shell"],
    )
    skill = build_skill("shell-skill")

    with pytest.raises(RuntimeError) as exc:
        await executor.execute(
            context=context,
            skill=skill,
            tool_name="shell.run",
            arguments={"command": "ls"},
        )

    assert "blocked by sandbox policy" in str(exc.value)


@pytest.mark.asyncio
async def test_tool_executor_allows_shell_run_in_inline_sandbox():
    executor = ToolExecutor(
        sandbox_executor=SandboxExecutor(sandbox_mode="inline"),
    )
    context = ExecutionContext(
        task_id="task-005",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
        allowed_capabilities=["shell"],
    )
    skill = build_skill("shell-skill")

    result = await executor.execute(
        context=context,
        skill=skill,
        tool_name="shell.run",
        arguments={"command": "ls"},
    )

    assert result["tool_name"] == "shell.run"
    assert result["status"] == "ok"
    assert result["metadata"]["sandbox_mode"] == "inline"