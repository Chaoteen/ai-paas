from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MOVED_OUT_OF_FORMAL_PATHS = [
    REPO_ROOT / "gateway" / "prompt_execution_gateway.py",
    REPO_ROOT / "agent_core" / "core.py",
    REPO_ROOT / "agent_core" / "memory.py",
    REPO_ROOT / "agent_core" / "reasoning.py",
    REPO_ROOT / "agent_core" / "skills",
]

ARCHIVE_EXPECTED = [
    REPO_ROOT / "archive" / "legacy" / "gateway_compat" / "prompt_execution_gateway.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_runtime" / "core.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_runtime" / "memory.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_runtime" / "reasoning.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_runtime" / "skills",
]

def test_second_archive_batch_removed_from_formal_paths():
    still_present = [str(p.relative_to(REPO_ROOT)) for p in MOVED_OUT_OF_FORMAL_PATHS if p.exists()]
    assert not still_present, "files still present in formal paths:\n" + "\n".join(still_present)

def test_second_archive_batch_present_in_archive():
    missing = [str(p.relative_to(REPO_ROOT)) for p in ARCHIVE_EXPECTED if not p.exists()]
    assert not missing, "archived files missing from archive/legacy:\n" + "\n".join(missing)
