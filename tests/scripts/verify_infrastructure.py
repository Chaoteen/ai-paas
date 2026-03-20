#!/usr/bin/env python3
"""
基础设施与主线运行检查脚本

目标：
- 只检查当前正式主线依赖与入口
- 不再检查已归档的 legacy 进程名（如 router_bridge）
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path


RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"


def check_port(host: str, port: int, name: str) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    try:
        sock.connect((host, port))
        print(f"{GREEN}✓{RESET} {name}: {host}:{port} 可访问")
        return True
    except Exception:
        print(f"{RED}✗{RESET} {name}: {host}:{port} 不可访问")
        return False
    finally:
        sock.close()


def check_redis() -> bool:
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and "PONG" in result.stdout:
            print(f"{GREEN}✓{RESET} Redis: PONG")
            return True
        print(f"{RED}✗{RESET} Redis: 未返回 PONG")
        return False
    except Exception as exc:
        print(f"{YELLOW}⚠{RESET} Redis: 检查失败 - {exc}")
        return False


def check_opa_policy() -> bool:
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "http://127.0.0.1:8181/v1/policies",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"{GREEN}✓{RESET} OPA Policy: 已加载策略响应")
            return True
        print(f"{RED}✗{RESET} OPA Policy: 未获得有效响应")
        return False
    except Exception as exc:
        print(f"{YELLOW}⚠{RESET} OPA Policy: 检查失败 - {exc}")
        return False


def check_process(pattern: str, display_name: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().splitlines()[0]
            print(f"{GREEN}✓{RESET} {display_name}: 进程运行中 (PID: {pid})")
            return True
        print(f"{RED}✗{RESET} {display_name}: 进程未运行")
        return False
    except Exception as exc:
        print(f"{YELLOW}⚠{RESET} {display_name}: 无法检查进程 - {exc}")
        return False


def check_formal_scripts_exist() -> bool:
    repo_root = Path(__file__).resolve().parents[2]
    expected = [
        repo_root / "run_ai_platform_v4.sh",
        repo_root / "start_core_services.sh",
        repo_root / "start_infra.sh",
        repo_root / "start_frontend.sh",
    ]
    missing = [str(p.relative_to(repo_root)) for p in expected if not p.exists()]
    if missing:
        print(f"{RED}✗{RESET} Formal scripts: 缺失 -> {', '.join(missing)}")
        return False
    print(f"{GREEN}✓{RESET} Formal scripts: 启动脚本存在")
    return True


def main() -> int:
    results: list[bool] = []

    print(f"{BLUE}AI-PaaS 主线基础设施检查{RESET}")
    print("=" * 48)

    # === 基础设施层 ===
    print(f"{BLUE}【一、基础设施层】{RESET}")
    print("-" * 40)

    print("\n[1/8] 检查 Redis...")
    results.append(check_redis())

    print("\n[2/8] 检查 OPA 服务...")
    results.append(check_port("127.0.0.1", 8181, "OPA"))

    print("\n[3/8] 检查 OPA 策略...")
    results.append(check_opa_policy())

    # === 正式主线脚本 ===
    print(f"\n{BLUE}【二、正式启动脚本】{RESET}")
    print("-" * 40)

    print("\n[4/8] 检查正式启动脚本...")
    results.append(check_formal_scripts_exist())

    # === Runtime / Gateway 层 ===
    print(f"\n{BLUE}【三、主线运行层】{RESET}")
    print("-" * 40)

    print("\n[5/8] 检查 Gateway...")
    results.append(check_port("127.0.0.1", 8000, "Gateway"))

    print("\n[6/8] 检查 Frontend...")
    results.append(check_port("127.0.0.1", 5173, "Frontend Vite"))

    print("\n[7/8] 检查主线 Python 进程（main.py）...")
    results.append(check_process("python.*main.py|uvicorn.*main:app", "Main App"))

    print("\n[8/8] 检查主线前端进程（vite）...")
    results.append(check_process("vite", "Frontend Vite Process"))

    # === 汇总 ===
    passed = sum(1 for item in results if item)
    total = len(results)

    print(f"\n{BLUE}【汇总】{RESET}")
    print("-" * 40)
    print(f"通过: {passed}/{total}")

    if passed == total:
        print(f"{GREEN}✓ 所有主线基础设施检查通过{RESET}")
        return 0

    print(f"{YELLOW}⚠ 存在未通过项，请按主线启动顺序排查{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
