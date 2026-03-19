from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_GATEWAY_FILES = [
    REPO_ROOT / "gateway" / "prompt_execution_gateway.py",
]

def test_legacy_gateway_modules_have_governance_marker():
    missing = []
    for path in LEGACY_GATEWAY_FILES:
        assert path.exists(), f"missing expected legacy gateway file: {path}"
        content = path.read_text(encoding="utf-8")
        if "LEGACY GATEWAY COMPATIBILITY ENTRYPOINT" not in content:
            missing.append(str(path.relative_to(REPO_ROOT)))

    assert not missing, "legacy gateway modules missing governance marker:\\n" + "\\n".join(missing)
