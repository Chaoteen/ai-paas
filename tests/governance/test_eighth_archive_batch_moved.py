from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REMOVED_PATHS = [
    ROOT / "agent_core" / "__init__.py",
    ROOT / "services" / "server" / "__init__.py",
]

ARCHIVED_PATHS = [
    ROOT / "archive" / "legacy" / "package_stubs" / "agent_core.__init__.py",
    ROOT / "archive" / "legacy" / "package_stubs" / "services.server.__init__.py",
]


def test_eighth_archive_batch_removed_from_formal_paths():
    for path in REMOVED_PATHS:
        assert not path.exists(), f"expected formal path to be removed: {path}"


def test_eighth_archive_batch_present_in_archive():
    for path in ARCHIVED_PATHS:
        assert path.exists(), f"expected archived file missing: {path}"
