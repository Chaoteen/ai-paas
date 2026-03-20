from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_SCRIPT_ARTIFACTS = [
    REPO_ROOT / "run_ai_platform_v2.sh.bak.1770299180",
    REPO_ROOT / "run_ai_platform_v3.sh.bak",
    REPO_ROOT / "run_ai_platform_v4.sh.broken",
    REPO_ROOT / "start_core_services.sh.bak",
]

def test_legacy_script_artifacts_inventory_exists():
    missing = [str(p.relative_to(REPO_ROOT)) for p in LEGACY_SCRIPT_ARTIFACTS if not p.exists()]
    assert not missing, (
        "expected legacy script artifacts not found; update governance inventory if files moved/removed:\n"
        + "\n".join(missing)
    )
