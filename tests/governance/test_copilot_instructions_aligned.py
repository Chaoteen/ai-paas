from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_copilot_instructions_do_not_describe_legacy_stack_as_active() -> None:
    path = ROOT / ".github/copilot-instructions.md"
    assert path.exists(), f"missing file: {path}"

    text = path.read_text(encoding="utf-8")

    forbidden_active_refs = [
        "agent_core/memory.py",
        "agent_core/envelope_bus.py",
        "services/server/agent_service.py",
        "task_manager.py",
        "agent_manager.py",
        "start_agent_system.py",
        "Create in `agent_core/skills/`",
        "run_ai_platform.sh start   # Launches Redis bus, LangGraph, router_bridge, agent system",
    ]

    for item in forbidden_active_refs:
        assert item not in text, f"copilot instructions still reference legacy active path: {item}"


def test_copilot_instructions_describe_formal_mainline() -> None:
    path = ROOT / ".github/copilot-instructions.md"
    text = path.read_text(encoding="utf-8")

    required_markers = [
        "Gateway API -> Task Submission Service -> Task Store / Outbox -> Redis Queue -> Runtime Workers",
        "archive/legacy/",
        "run_ai_platform_v4.sh",
        "pytest tests/governance -q",
        "pytest tests/runtime tests/gateway -q",
    ]

    for item in required_markers:
        assert item in text, f"copilot instructions missing required formal marker: {item}"
