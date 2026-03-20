from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FORMAL_PATHS_REMOVED = [
    "api/v1/flowise_bridge.py.bak",
    "control_plane/架构信息.txt",
    "flowise/README.md.txt",
    "project_tree.txt",
    "promptflow/PromptFlow服务部署与集成文档.docx",
    "promptflow/promptflow产品文档.docx",
    "proto/proto生成SDK方法.txt",
    "run_ai_platform_v4.sh.bak.freeze_legacy",
    "start_core_services.sh.bak.freeze_legacy",
    "logs/agent.log",
    "logs/agent_system.log",
    "logs/bus.log",
    "logs/frontend.log",
    "logs/gateway.log",
    "logs/langgraph.log",
    "logs/model_worker.log",
    "logs/ollama.log",
    "logs/redis_bus.log",
    "logs/router.log",
    "logs/router_bridge.log",
    "logs/worker.log",
    "promptflow/test_flow/.promptflow/flow.log",
]

ARCHIVED_PATHS_PRESENT = [
    "archive/legacy/loose_artifacts/flowise_bridge.py.bak",
    "archive/legacy/loose_artifacts/README.md.txt",
    "archive/legacy/loose_artifacts/project_tree.txt",
    "archive/legacy/control_plane_docs/架构信息.txt",
    "archive/legacy/promptflow_docs/PromptFlow服务部署与集成文档.docx",
    "archive/legacy/promptflow_docs/promptflow产品文档.docx",
    "archive/legacy/proto_docs/proto生成SDK方法.txt",
    "archive/legacy/scripts/run_ai_platform_v4.sh.bak.freeze_legacy",
    "archive/legacy/scripts/start_core_services.sh.bak.freeze_legacy",
    "archive/legacy/log_snapshots/logs/agent.log",
    "archive/legacy/log_snapshots/logs/agent_system.log",
    "archive/legacy/log_snapshots/logs/bus.log",
    "archive/legacy/log_snapshots/logs/frontend.log",
    "archive/legacy/log_snapshots/logs/gateway.log",
    "archive/legacy/log_snapshots/logs/langgraph.log",
    "archive/legacy/log_snapshots/logs/model_worker.log",
    "archive/legacy/log_snapshots/logs/ollama.log",
    "archive/legacy/log_snapshots/logs/redis_bus.log",
    "archive/legacy/log_snapshots/logs/router.log",
    "archive/legacy/log_snapshots/logs/router_bridge.log",
    "archive/legacy/log_snapshots/logs/worker.log",
    "archive/legacy/log_snapshots/promptflow/flow.log",
]


def test_sixth_archive_batch_removed_from_formal_paths() -> None:
    for relative_path in FORMAL_PATHS_REMOVED:
        path = ROOT / relative_path
        assert not path.exists(), f"expected formal path removed: {path}"


def test_sixth_archive_batch_present_in_archive() -> None:
    for relative_path in ARCHIVED_PATHS_PRESENT:
        path = ROOT / relative_path
        assert path.exists(), f"expected archived file missing: {path}"
