from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_SCRIPTS = ROOT / "archive" / "legacy" / "scripts"


EXPECTED_SCRIPT_ARTIFACTS = [
    "run_ai_platform_v2.sh.bak.1770299180",
    "run_ai_platform_v3.sh.bak",
    "run_ai_platform_v4.sh.broken",
    "start_core_services.sh.bak",
]


def test_legacy_script_artifacts_inventory_exists() -> None:
    missing = [
        name for name in EXPECTED_SCRIPT_ARTIFACTS
        if not (ARCHIVE_SCRIPTS / name).exists()
    ]
    assert not missing, (
        "expected legacy script artifacts not found; update governance inventory if files moved/removed:\n"
        + "\n".join(missing)
    )
