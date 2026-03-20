from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_TARGETS = [
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "handlers" / "agent_handler.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "handlers" / "model_handler.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "handlers" / "promptflow_handler.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "adapters" / "agent_core_adapter.py",
    REPO_ROOT / "archive" / "legacy" / "data_plane_execution" / "legacy" / "router_bridge_adapter.py",
]

REQUIRED_MARKER = "LEGACY COMPATIBILITY MODULE"

def test_legacy_modules_have_governance_marker():
    missing = []
    marker_missing = []

    for path in LEGACY_TARGETS:
        if not path.exists():
            missing.append(str(path.relative_to(REPO_ROOT)))
            continue

        content = path.read_text(encoding="utf-8")
        if REQUIRED_MARKER not in content:
            marker_missing.append(str(path.relative_to(REPO_ROOT)))

    assert not missing, "missing expected legacy target:\n" + "\n".join(missing)
    assert not marker_missing, "legacy modules missing governance marker:\n" + "\n".join(marker_missing)
