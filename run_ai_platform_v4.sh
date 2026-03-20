#!/bin/bash
# FORMAL PLATFORM ENTRYPOINT
# Status:
# - Sole formal full-stack launcher for release governance
# - Coordinates infra / containers / core services / frontend
# - All previous run_ai_platform*.sh variants are deprecated wrappers or legacy artifacts
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info()  { echo -e "\033[1;32m[MASTER]\033[0m $1"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

check_scripts() {
  local scripts=("start_infra.sh" "start_containers.sh" "start_core_services.sh" "start_frontend.sh")
  for script in "${scripts[@]}"; do
    if [[ ! -f "$SCRIPT_DIR/$script" ]]; then
      log_error "缺少子脚本: $script"
      exit 1
    fi
    chmod +x "$SCRIPT_DIR/$script"
  done
}

print_status() {
  echo "=== AI PaaS V4 状态 ==="

  echo "--- 基础设施 ---"
  if pgrep -f "ollama serve" > /dev/null; then
    echo "✅ Ollama"
  else
    echo "❌ Ollama"
  fi

  docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "redis|opa" || echo "⚠️ Redis/OPA 容器未运行"

  echo "--- 容器应用 ---"
  docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "postgres|promptflow|flowise" || echo "⚠️ 应用容器未运行"

  echo "--- 核心服务 (Python) ---"
  if pgrep -f "uvicorn main:app" > /dev/null; then
    PID=$(pgrep -f "uvicorn main:app" | head -n 1)
    echo "✅ API Gateway (Port 8000) [PID: $PID]"
  else
    echo "❌ API Gateway (Port 8000)"
  fi

  echo "ℹ️ Legacy Agent System: DISABLED BY GOVERNANCE"
  echo "ℹ️ Legacy RouterBridge / RedisBus: NOT PART OF FORMAL STARTUP"
}

case "${1:-start}" in
  start)
    log_info "开始启动 AI PaaS V4（正式版收敛模式）..."
    check_scripts

    log_info "[1/4] 启动基础设施 (Ollama, Redis, OPA)..."
    "$SCRIPT_DIR/start_infra.sh" start

    log_info "[2/4] 启动容器应用 (DB, PromptFlow, Flowise)..."
    "$SCRIPT_DIR/start_containers.sh" start

    log_info "[3/4] 启动核心服务 (Python Microservices)..."
    "$SCRIPT_DIR/start_core_services.sh" start

    log_info "[4/4] 检查前端..."
    "$SCRIPT_DIR/start_frontend.sh" start

    log_info "✅ 全栈启动完成"
    log_info "访问 Flowise: http://localhost:3000"
    log_info "API 文档: http://localhost:8000/docs"
    log_info "运行 './run_ai_platform_v4.sh status' 查看状态"
    ;;
  stop)
    log_info "开始停止所有服务..."
    check_scripts || true
    "$SCRIPT_DIR/start_frontend.sh" stop || true
    "$SCRIPT_DIR/start_core_services.sh" stop || true
    "$SCRIPT_DIR/start_containers.sh" stop || true
    "$SCRIPT_DIR/start_infra.sh" stop || true
    log_info "✅ 所有服务已停止"
    ;;
  restart)
    log_info "重启所有服务..."
    "$0" stop
    sleep 3
    "$0" start
    ;;
  status)
    print_status
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
