from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MOVED_OUT_OF_FORMAL_PATHS = [
    REPO_ROOT / "app.py",
    REPO_ROOT / "control_plane" / "prompt_execution_gateway.py",
    REPO_ROOT / "data_plane" / "router.py",
    REPO_ROOT / "data_plane" / "envelope.py",
    REPO_ROOT / "data_plane" / "result.py",
    REPO_ROOT / "data_plane" / "dispatcher.py",
    REPO_ROOT / "data_plane" / "agent_worker.py",
    REPO_ROOT / "data_plane" / "router_worker.py",
    REPO_ROOT / "data_plane" / "handlers",
    REPO_ROOT / "data_plane" / "adapters",
    REPO_ROOT / "data_plane" / "legacy",
    REPO_ROOT / "tests" / "test_agent_worker.py",
    REPO_ROOT / "tests" / "test_router_worker.py",
    REPO_ROOT / "tests" / "test_data_plane_router.py",
    REPO_ROOT / "tests" / "test_core_models.py",
]

ARCHIVE_EXPECTED = [
    REPO_ROOT / "archive" / "legacy" / "control_plane_gateway" / "app.py",
    REPO_ROOT / "archive" / "legacy" / "control_plane_gateway" / "prompt_execution_gateway.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "router.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "envelope.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "result.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "dispatcher.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "agent_worker.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "router_worker.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "handlers",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "adapters",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "legacy",
    REPO_ROOT / "archive" / "legacy" / "tests_data_plane_execution" / "test_agent_worker.py",
    REPO_ROOT / "archive" / "legacy" / "tests_data_plane_execution" / "test_router_worker.py",
    REPO_ROOT / "archive" / "legacy" / "tests_data_plane_execution" / "test_data_plane_router.py",
    REPO_ROOT / "archive" / "legacy" / "tests_data_plane_execution" / "test_core_models.py",
]

def test_third_archive_batch_removed_from_formal_paths():
    still_present = [str(p.relative_to(REPO_ROOT)) for p in MOVED_OUT_OF_FORMAL_PATHS if p.exists()]
    assert not still_present, "files still present in formal paths:\n" + "\n".join(still_present)

def test_third_archive_batch_present_in_archive():
    missing = [str(p.relative_to(REPO_ROOT)) for p in ARCHIVE_EXPECTED if not p.exists()]
    assert not missing, "archived files missing from archive/legacy:\n" + "\n".join(missing)
