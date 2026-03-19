from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_TARGETS = [
    REPO_ROOT / "data_plane" / "adapters" / "agent_core_adapter.py",
    REPO_ROOT / "data_plane" / "legacy" / "router_bridge_adapter.py",
    REPO_ROOT / "data_plane" / "handlers" / "agent_handler.py",
    REPO_ROOT / "data_plane" / "handlers" / "model_handler.py",
    REPO_ROOT / "data_plane" / "handlers" / "promptflow_handler.py",
]

def test_legacy_modules_have_governance_marker():
    missing = []
    for path in LEGACY_TARGETS:
        assert path.exists(), f"missing expected legacy target: {path}"
        content = path.read_text(encoding="utf-8")
        if "LEGACY COMPATIBILITY MODULE" not in content:
            missing.append(str(path.relative_to(REPO_ROOT)))

    assert not missing, "legacy modules missing governance marker:\\n" + "\\n".join(missing)
