from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REMOVED_PATHS = [
    REPO_ROOT / "docs" / "runtime_phase7_handover.md",
    REPO_ROOT / "docs" / "runtime_phase12_handover.md",
]

ARCHIVED_PATHS = [
    REPO_ROOT / "archive" / "legacy" / "historical_runtime_docs" / "runtime_phase7_handover.md",
    REPO_ROOT / "archive" / "legacy" / "historical_runtime_docs" / "runtime_phase12_handover.md",
]


def test_ninth_archive_batch_removed_from_formal_paths():
    for path in REMOVED_PATHS:
        assert not path.exists(), f"expected formal path to be removed: {path}"


def test_ninth_archive_batch_present_in_archive():
    for path in ARCHIVED_PATHS:
        assert path.exists(), f"expected archived file missing: {path}"
