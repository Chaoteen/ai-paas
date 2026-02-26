#!/bin/bash
# start_core_services.sh: 启动 Python 微服务群
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/pids"
VENV_PATH="${VENV_PATH:-$SCRIPT_DIR/.venv}"

mkdir -p "$LOG_DIR" "$PID_DIR"

log_info() { echo -e "\033[0;35m[CORE]\033[0m $1"; }

# 激活虚拟环境
activate_venv() {
  if [[ -f "$VENV_PATH/bin/activate" ]]; then
    source "$VENV_PATH/bin/activate"
  elif command -v conda &> /dev/null; then
    conda activate base 2>/dev/null || true
  fi
}

start_service() {
  local name=$1; local cmd=$2; local pidfile=$3; local logfile=$4; local pattern=$5
  log_info "🚀 启动 $name..."
  if pgrep -f "$pattern" > /dev/null; then
    log_info "✅ $name 已在运行"
    return 0
  fi
  cd "$SCRIPT_DIR"
  nohup bash -lc "$cmd" > "$logfile" 2>&1 &
  echo $! > "$pidfile"
  sleep 2
  if pgrep -f "$pattern" > /dev/null; then
    log_info "✅ $name 启动成功 (PID: $(cat $pidfile))"
  else
    log_info "❌ $name 启动失败"
  fi
}

# --- Main Start ---
start_all() {
  activate_venv
  
  # 1. Redis Bus
  start_service "RedisBus" "python agent_core/run_bus.py" "$PID_DIR/bus.pid" "$LOG_DIR/bus.log" "run_bus.py"
  
  # 2. RouterBridge
  start_service "RouterBridge" "python agent_core/router_bridge.py" "$PID_DIR/router.pid" "$LOG_DIR/router.log" "router_bridge.py"
  
  # 3. ModelWorker
  start_service "ModelWorker" "python workers/model_worker.py" "$PID_DIR/worker.pid" "$LOG_DIR/worker.log" "model_worker.py"
  
  # 4. AgentSystem (API Gateway) - 最后启动，依赖其他服务
  sleep 3
  if [[ -f "$SCRIPT_DIR/services/server/start_agent_system.py" ]]; then
    start_service "AgentSystem" "uvicorn services.server.start_agent_system:app --host 0.0.0.0 --port 8000" "$PID_DIR/agent.pid" "$LOG_DIR/agent.log" "start_agent_system.py"
  fi
}

# --- Stop ---
stop_all() {
  log_info "停止核心服务..."
  for pidfile in "$PID_DIR"/*.pid; do
    if [[ -f "$pidfile" ]]; then
      kill $(cat "$pidfile") 2>/dev/null || true
      rm "$pidfile"
    fi
  done
  pkill -f "run_bus.py" || true
  pkill -f "router_bridge.py" || true
  pkill -f "model_worker.py" || true
  pkill -f "start_agent_system.py" || true
  log_info "✅ 核心服务已停止"
}

case "${1:-start}" in
  start) start_all ;;
  stop) stop_all ;;
  restart) stop_all; sleep 2; start_all ;;
  *) echo "用法: $0 {start|stop|restart}"; exit 1 ;;
esac