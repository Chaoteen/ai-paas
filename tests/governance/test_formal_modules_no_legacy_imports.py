from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORMAL_FILES = [
    REPO_ROOT / "bootstrap" / "runtime_bootstrap.py",
    REPO_ROOT / "gateway" / "main.py",
    REPO_ROOT / "gateway" / "api" / "tasks.py",
    REPO_ROOT / "gateway" / "api" / "agent_runtime.py",
    REPO_ROOT / "gateway" / "api" / "generation.py",
    REPO_ROOT / "gateway" / "api" / "health.py",
    REPO_ROOT / "gateway" / "api" / "ui.py",
]

FORBIDDEN_PATTERNS = [
    "from agent_core",
    "import agent_core",
    "from services.server",
    "import services.server",
    "from data_plane.adapters.agent_core_adapter",
    "import data_plane.adapters.agent_core_adapter",
    "from data_plane.legacy.router_bridge_adapter",
    "import data_plane.legacy.router_bridge_adapter",
    "from data_plane.handlers.agent_handler",
    "import data_plane.handlers.agent_handler",
    "from data_plane.handlers.model_handler",
    "import data_plane.handlers.model_handler",
    "from data_plane.handlers.promptflow_handler",
    "import data_plane.handlers.promptflow_handler",
]

def test_formal_modules_do_not_import_legacy_stack():
    missing = [str(p.relative_to(REPO_ROOT)) for p in FORMAL_FILES if not p.exists()]
    assert not missing, "formal files missing:\\n" + "\\n".join(missing)

    violations = []

    for path in FORMAL_FILES:
        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in content:
                violations.append(f"{path.relative_to(REPO_ROOT)} -> {pattern}")

    assert not violations, "formal modules still import legacy stack:\\n" + "\\n".join(violations)
