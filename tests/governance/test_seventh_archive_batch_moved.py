from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORMAL_REMOVED = [
    ROOT / "docs" / "runtime_phase8_checkpoint.md",
    ROOT / "docs" / "runtime_handoff_phase13.md",
]

ARCHIVED_PRESENT = [
    ROOT / "archive" / "legacy" / "historical_runtime_docs" / "runtime_phase8_checkpoint.md",
    ROOT / "archive" / "legacy" / "historical_runtime_docs" / "runtime_handoff_phase13.md",
]


def test_seventh_archive_batch_removed_from_formal_paths():
    for path in FORMAL_REMOVED:
        assert not path.exists(), f"expected formal path removed: {path}"


def test_seventh_archive_batch_present_in_archive():
    for path in ARCHIVED_PRESENT:
        assert path.exists(), f"expected archived file missing: {path}"
