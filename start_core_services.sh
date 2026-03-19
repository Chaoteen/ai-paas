#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

log_info() { echo -e "\033[1;36m[CORE-SVC]\033[0m $1"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

CONDA_ENV="qwen"
CONDA_BASE=$(conda info --base 2>/dev/null || true)

if [[ -z "${CONDA_BASE:-}" ]]; then
  log_error "无法找到 Conda 安装路径。请先确认 conda 可用。"
  exit 1
fi

CONDA_INIT_SCRIPT="$CONDA_BASE/etc/profile.d/conda.sh"

start_gateway() {
  log_info "启动 API Gateway (Uvicorn on port 8000)..."

  if pgrep -f "uvicorn main:app" > /dev/null; then
    log_info "⚠️ API Gateway 已在运行，跳过。"
    return 0
  fi

  if [[ ! -f "$PROJECT_ROOT/main.py" ]]; then
    log_error "在 $PROJECT_ROOT 下找不到 main.py"
    exit 1
  fi

  local START_CMD
  START_CMD="cd '$PROJECT_ROOT' && source '$CONDA_INIT_SCRIPT' && conda activate '$CONDA_ENV' && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

  nohup bash -c "$START_CMD" > "$LOG_DIR/gateway.log" 2>&1 &
  local GATEWAY_PID=$!

  sleep 3

  if ps -p "$GATEWAY_PID" > /dev/null; then
    log_info "✅ API Gateway 启动成功 (PID: $GATEWAY_PID)"
    if ! ss -tulpn 2>/dev/null | grep -q ":8000 "; then
      log_error "进程存在，但端口 8000 未监听，请检查日志："
      tail -n 20 "$LOG_DIR/gateway.log" || true
      exit 1
    fi
  else
    log_error "API Gateway 启动失败。最后 20 行日志："
    tail -n 20 "$LOG_DIR/gateway.log" || true
    exit 1
  fi
}

stop_gateway() {
  if pgrep -f "uvicorn main:app" > /dev/null; then
    pkill -f "uvicorn main:app"
    log_info "⏹️ API Gateway 已停止"
  else
    log_info "⚠️ API Gateway 未运行"
  fi
}

print_governance_notice() {
  log_info "ℹ️ 正式版收敛策略已启用"
  log_info "ℹ️ 当前脚本仅管理正式主干组件"
  log_info "ℹ️ 历史链路已从默认启动流程中移除"
}

case "${1:-start}" in
  start)
    log_info "正在启动核心服务..."
    start_gateway
    print_governance_notice
    log_info "核心服务启动完毕。"
    ;;
  stop)
    log_info "正在停止核心服务..."
    stop_gateway
    print_governance_notice
    log_info "核心服务已停止。"
    ;;
  status)
    echo "=== Core Services Status ==="
    if pgrep -f "uvicorn main:app" > /dev/null; then
      PID=$(pgrep -f "uvicorn main:app" | head -n 1)
      echo "✅ API Gateway (PID: $PID)"
    else
      echo "❌ API Gateway"
    fi
    echo "ℹ️ Legacy stack: disabled by governance"
    ;;
  *)
    echo "用法: $0 {start|stop|status}"
    exit 1
    ;;
esac
