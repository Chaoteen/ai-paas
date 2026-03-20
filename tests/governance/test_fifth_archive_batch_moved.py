from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


FORMAL_PATHS_REMOVED = [
    REPO_ROOT / "agent_core" / "analyze_models.py",
    REPO_ROOT / "agent_core" / "checkmodel.py",
    REPO_ROOT / "agent_core" / "Router_bridge的作用说明.txt",
    REPO_ROOT / "agent_core" / "agent.txt",
    REPO_ROOT / "agent_core" / "agent说明.docx",
    REPO_ROOT / "agent_core" / "config.yaml.txt",
    REPO_ROOT / "agent_core" / "redis_bus的说明.txt",
    REPO_ROOT / "agent_core" / "redis和agent启动方式.txt",
    REPO_ROOT / "agent_core" / "启动和关闭deepseek.txt",
    REPO_ROOT / "services" / "server" / "agent_service.py",
    REPO_ROOT / "services" / "server" / "deepseek_service.py",
    REPO_ROOT / "services" / "server" / "deepseek_service.py.txt",
    REPO_ROOT / "services" / "server" / "工作日志.txt",
    REPO_ROOT / "services" / "server" / "请求到agent再到模型的链路.txt",
]


ARCHIVED_PATHS_PRESENT = [
    REPO_ROOT / "archive" / "legacy" / "agent_core_tools" / "analyze_models.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_tools" / "checkmodel.py",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "Router_bridge的作用说明.txt",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "agent.txt",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "agent说明.docx",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "config.yaml.txt",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "redis_bus的说明.txt",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "redis和agent启动方式.txt",
    REPO_ROOT / "archive" / "legacy" / "agent_core_misc" / "启动和关闭deepseek.txt",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "agent_service.py",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "deepseek_service.py",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "deepseek_service.py.txt",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "工作日志.txt",
    REPO_ROOT / "archive" / "legacy" / "services_server_runtime" / "请求到agent再到模型的链路.txt",
]


def test_fifth_archive_batch_removed_from_formal_paths():
    for path in FORMAL_PATHS_REMOVED:
        assert not path.exists(), f"expected file moved out of formal path: {path}"


def test_fifth_archive_batch_present_in_archive():
    for path in ARCHIVED_PATHS_PRESENT:
        assert path.exists(), f"expected archived file missing: {path}"