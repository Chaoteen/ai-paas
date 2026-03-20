from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MOVED_OUT_OF_FORMAL_PATHS = [
    REPO_ROOT / "run_ai_platform_v2.sh.bak.1770299180",
    REPO_ROOT / "run_ai_platform_v3.sh.bak",
    REPO_ROOT / "run_ai_platform_v4.sh.broken",
    REPO_ROOT / "start_core_services.sh.bak",
    REPO_ROOT / "services" / "server" / "start_agent_system.py",
    REPO_ROOT / "services" / "server" / "task_manager.py",
    REPO_ROOT / "services" / "server" / "agent_manager.py",
    REPO_ROOT / "services" / "server" / "agent_registry.py",
    REPO_ROOT / "services" / "server" / "model_service.py",
    REPO_ROOT / "services" / "server" / "test_client.py",
    REPO_ROOT / "agent_core" / "router_bridge.py",
    REPO_ROOT / "agent_core" / "router_bridge.py.bak",
    REPO_ROOT / "agent_core" / "redis_bus.py",
    REPO_ROOT / "agent_core" / "run_bus.py",
    REPO_ROOT / "agent_core" / "envelope_bus.py",
]

ARCHIVE_EXPECTED = [
    REPO_ROOT / "archive" / "legacy" / "scripts" / "run_ai_platform_v2.sh.bak.1770299180",
    REPO_ROOT / "archive" / "legacy" / "scripts" / "run_ai_platform_v3.sh.bak",
    REPO_ROOT / "archive" / "legacy" / "scripts" / "run_ai_platform_v4.sh.broken",
    REPO_ROOT / "archive" / "legacy" / "scripts" / "start_core_services.sh.bak",
    REPO_ROOT / "archive" / "legacy" / "services_server" / "start_agent_system.py",
    REPO_ROOT / "archive" / "legacy" / "services_server" / "task_manager.py",
    REPO_ROOT / "archive" / "legacy" / "services_server" / "agent_manager.py",
    REPO_ROOT / "archive" / "legacy" / "services_server" / "agent_registry.py",
    REPO_ROOT / "archive" / "legacy" / "services_server" / "model_service.py",
    REPO_ROOT / "archive" / "legacy" / "services_server" / "test_client.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_bus" / "router_bridge.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_bus" / "router_bridge.py.bak",
    REPO_ROOT / "archive" / "legacy" / "agent_core_bus" / "redis_bus.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_bus" / "run_bus.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_bus" / "envelope_bus.py",
]

def test_first_archive_batch_removed_from_formal_paths():
    still_present = [str(p.relative_to(REPO_ROOT)) for p in MOVED_OUT_OF_FORMAL_PATHS if p.exists()]
    assert not still_present, "files still present in formal paths:\n" + "\n".join(still_present)

def test_first_archive_batch_present_in_archive():
    missing = [str(p.relative_to(REPO_ROOT)) for p in ARCHIVE_EXPECTED if not p.exists()]
    assert not missing, "archived files missing from archive/legacy:\n" + "\n".join(missing)
