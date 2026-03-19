from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORMAL_ENTRYPOINTS = [
    REPO_ROOT / "start_core_services.sh",
    REPO_ROOT / "run_ai_platform_v4.sh",
]

FORBIDDEN_PATTERNS = [
    "start_agent_system.py",
    "router_bridge.py",
    "redis_bus.py",
    "run_bus.py",
    "services/server",
    "agent_core",
]

def test_formal_entrypoints_do_not_reference_legacy_stack():
    missing = [str(p) for p in FORMAL_ENTRYPOINTS if not p.exists()]
    assert not missing, f"formal entrypoint files missing: {missing}"

    violations = []

    for path in FORMAL_ENTRYPOINTS:
        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in content:
                violations.append(f"{path.name}: contains forbidden legacy reference -> {pattern}")

    assert not violations, "formal startup path still references legacy stack:\n" + "\n".join(violations)
