from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_bootstrap_does_not_import_legacy_workers():
    path = REPO_ROOT / "bootstrap" / "runtime_bootstrap.py"
    content = path.read_text(encoding="utf-8")

    forbidden = [
        "from data_plane.router_worker import RouterWorker",
        "from data_plane.agent_worker import AgentWorker",
    ]

    hits = [item for item in forbidden if item in content]
    assert not hits, "runtime_bootstrap still imports legacy embedded workers:\n" + "\n".join(hits)
