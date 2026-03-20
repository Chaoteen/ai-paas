from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORMAL = REPO_ROOT / "run_ai_platform_v4.sh"
DEPRECATED_WRAPPERS = [
    REPO_ROOT / "run_ai_platform.sh",
    REPO_ROOT / "run_ai_platform_v2.sh",
]

def test_formal_launcher_is_v4():
    assert FORMAL.exists(), "missing formal launcher run_ai_platform_v4.sh"
    content = FORMAL.read_text(encoding="utf-8")
    assert "FORMAL PLATFORM ENTRYPOINT" in content, (
        "run_ai_platform_v4.sh must be marked as the sole formal launcher"
    )

def test_deprecated_wrappers_forward_to_v4():
    missing = [str(p.relative_to(REPO_ROOT)) for p in DEPRECATED_WRAPPERS if not p.exists()]
    assert not missing, "missing deprecated wrappers:\n" + "\n".join(missing)

    violations = []
    for path in DEPRECATED_WRAPPERS:
        content = path.read_text(encoding="utf-8")
        if "[DEPRECATED]" not in content:
            violations.append(f"{path.name}: missing deprecation banner")
        if 'run_ai_platform_v4.sh' not in content:
            violations.append(f"{path.name}: missing forward target run_ai_platform_v4.sh")
        if 'exec "$SCRIPT_DIR/run_ai_platform_v4.sh"' not in content:
            violations.append(f"{path.name}: missing exec forward to v4")

    assert not violations, "deprecated wrapper violations:\n" + "\n".join(violations)
