#!/usr/bin/env python3
import subprocess
import sys
import os
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FLOWISE_DIR = os.path.join(BASE_DIR, "flowise")
COMPOSE_FILE = os.path.join(FLOWISE_DIR, "docker-compose.yml")

def run(cmd, cwd=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def docker_available():
    return run(["docker", "info"]).returncode == 0

def compose_up():
    print("🚀 启动 Flowise（docker compose）")
    run(["docker", "compose", "up", "-d"], cwd=FLOWISE_DIR)

def compose_down():
    print("🛑 停止 Flowise（保留数据）")
    run(["docker", "compose", "stop"], cwd=FLOWISE_DIR)

def compose_status():
    r = run(["docker", "compose", "ps"], cwd=FLOWISE_DIR)
    print(r.stdout)

def health_check():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:3000", timeout=3)
        print("✅ Flowise 健康")
    except Exception:
        print("⚠️ Flowise 未就绪")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: flowise_manager.py {start|stop|status|health}")
        sys.exit(1)

    if not docker_available():
        print("❌ Docker 不可用")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        compose_up()
        health_check()
    elif cmd == "stop":
        compose_down()
    elif cmd == "status":
        compose_status()
    elif cmd == "health":
        health_check()
    else:
        print("未知命令")
