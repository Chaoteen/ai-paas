from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COPILOT = ROOT / ".github" / "copilot-instructions.md"


def test_copilot_instructions_keep_archive_generic():
    text = COPILOT.read_text(encoding="utf-8")

    forbidden = [
        "agent_core/",
        "services/server/",
        "prompt_execution_gateway.py",
        "data_plane/router.py",
        "router_worker.py",
        "data_plane/handlers/",
        "router_bridge",
        "redis_bus",
        "start_agent_system.py",
        "task_manager.py",
        "agent_manager.py",
        "agent_registry.py",
    ]

    for item in forbidden:
        assert item not in text, f"copilot instructions should not reintroduce legacy path wording: {item}"


def test_copilot_instructions_describe_formal_mainline_targets():
    text = COPILOT.read_text(encoding="utf-8")

    required = [
        "gateway/",
        "runtime/",
        "control_plane/",
        "bootstrap/",
        "webapp/",
        "archive/legacy/",
        "http://localhost:5173",
        "run_ai_platform_v4.sh",
        "start_frontend.sh",
    ]

    for item in required:
        assert item in text, f"copilot instructions missing formal mainline guidance: {item}"
