from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORMAL_PATHS_REMOVED = [
    REPO_ROOT / "agent_core" / "analyze_models.py",
    REPO_ROOT / "agent_core" / "checkmodel.py",
    REPO_ROOT / "services" / "server" / "agent_service.py",
    REPO_ROOT / "services" / "server" / "deepseek_service.py",
]

ARCHIVE_PATHS_PRESENT = [
    REPO_ROOT / "archive" / "legacy" / "agent_core_tools" / "analyze_models.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_tools" / "checkmodel.py",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "agent_service.py",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "deepseek_service.py",
]


def test_fourth_archive_batch_removed_from_formal_paths():
    for path in FORMAL_PATHS_REMOVED:
        assert not path.exists(), f"formal path should have been removed: {path}"


def test_fourth_archive_batch_present_in_archive():
    for path in ARCHIVE_PATHS_PRESENT:
        assert path.exists(), f"archived path missing: {path}"
