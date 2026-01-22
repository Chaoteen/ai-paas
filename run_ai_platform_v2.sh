#!/bin/bash
# ai-os/run_ai_platform_v2.sh
# 多租户 + ABAC + Streams 联调闭环启动脚本（最终版）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

# --- PIDs ---
REDIS_BUS_PID="$PID_DIR/redis_bus.pid"
LANGGRAPH_PID="$PID_DIR/langgraph.pid"
ROUTER_BRIDGE_PID="$PID_DIR/router_bridge.pid"
MODEL_WORKER_PID="$PID_DIR/model_worker.pid"
AGENT_SYSTEM_PID="$PID_DIR/agent_system.pid"

# --- ENV（可按需改）---
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
export SOURCE_STREAM="${SOURCE_STREAM:-agent.tasks.stream}"
export SOURCE_GROUP="${SOURCE_GROUP:-router_workers}"
export DEST_STREAM="${DEST_STREAM:-agent.processed.tasks.stream}"
export RESULT_STREAM="${RESULT_STREAM:-agent.result.stream}"

export LANGGRAPH_SERVICE_URL="${LANGGRAPH_SERVICE_URL:-localhost:50051}"
export PROMPTFLOW_SERVICE_URL="${PROMPTFLOW_SERVICE_URL:-http://localhost:8081}"

# model worker
export MODEL_WORKER_GROUP="${MODEL_WORKER_GROUP:-model_workers}"
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
export DEFAULT_MODEL_ID="${DEFAULT_MODEL_ID:-deepseek-r1:latest}"

# --- helpers ---
is_running() { pgrep -f "$1" >/dev/null 2>&1; }

start_proc() {
  local name="$1"
  local workdir="$2"
  local cmd="$3"
  local pidfile="$4"
  local logfile="$5"
  local pattern="$6"
  local warmup="${7:-2}"

  echo "🚀 启动 $name ..."
  if is_running "$pattern"; then
    echo "✅ $name 已在运行"
    return 0
  fi

  (cd "$workdir" && nohup bash -lc "$cmd" >"$logfile" 2>&1 & echo $! >"$pidfile")
  sleep "$warmup"

  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
    echo "✅ $name 启动成功 (PID: $pid)"
    return 0
  fi

  echo "❌ $name 启动失败，查看日志: tail -f $logfile"
  return 1
}

stop_proc() {
  local name="$1"
  local pidfile="$2"
  local pattern="$3"

  echo "🛑 停止 $name ..."
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile" || true)"
    if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
      sleep 2
      ps -p "$pid" >/dev/null 2>&1 && kill -9 "$pid" || true
    fi
    rm -f "$pidfile"
  fi

  # 兜底：按pattern停
  if is_running "$pattern"; then
    pkill -f "$pattern" || true
    sleep 1
    pkill -9 -f "$pattern" 2>/dev/null || true
  fi

  echo "✅ $name 已停止"
}

status_proc() {
  local name="$1"
  local pattern="$2"
  if is_running "$pattern"; then
    local pid
    pid="$(pgrep -f "$pattern" | head -n 1)"
    echo "✅ $name 正在运行 (PID: $pid)"
  else
    echo "❌ $name 未运行"
  fi
}

start_all() {
  echo "🎯 启动 AI PaaS（v2 多租户+ABAC）..."

  echo "=== 1) Redis BUS ==="
  start_proc \
    "Redis消息总线(run_bus.py)" \
    "$SCRIPT_DIR/agent_core" \
    "python run_bus.py" \
    "$REDIS_BUS_PID" \
    "$LOG_DIR/redis_bus.log" \
    "run_bus.py" \
    3

  echo "=== 2) LangGraph（可选） ==="
  if [[ -f "$SCRIPT_DIR/langgraph/langgraph_grpc_server.py" ]]; then
    start_proc \
      "LangGraph服务" \
      "$SCRIPT_DIR" \
      "python langgraph/langgraph_grpc_server.py" \
      "$LANGGRAPH_PID" \
      "$LOG_DIR/langgraph.log" \
      "langgraph_grpc_server.py" \
      5 || true
  else
    echo "⚠️ 未找到 langgraph/langgraph_grpc_server.py，跳过"
  fi

  echo "=== 3) RouterBridge ==="
  start_proc \
    "RouterBridge" \
    "$SCRIPT_DIR/agent_core" \
    "python router_bridge.py" \
    "$ROUTER_BRIDGE_PID" \
    "$LOG_DIR/router_bridge.log" \
    "router_bridge.py" \
    3

  echo "=== 4) ModelWorker（必选：闭环） ==="
  start_proc \
    "ModelWorker" \
    "$SCRIPT_DIR" \
    "python workers/model_worker.py" \
    "$MODEL_WORKER_PID" \
    "$LOG_DIR/model_worker.log" \
    "workers/model_worker.py" \
    3

  echo "=== 5) AgentSystem（可选） ==="
  if [[ -f "$SCRIPT_DIR/server/start_agent_system.py" ]]; then
    start_proc \
      "Agent系统" \
      "$SCRIPT_DIR/server" \
      "python start_agent_system.py" \
      "$AGENT_SYSTEM_PID" \
      "$LOG_DIR/agent_system.log" \
      "start_agent_system.py" \
      3 || true
  else
    echo "⚠️ 未找到 server/start_agent_system.py，跳过"
  fi

  echo ""
  echo "📊 服务状态："
  status_proc "Redis消息总线" "run_bus.py"
  status_proc "LangGraph服务" "langgraph_grpc_server.py"
  status_proc "RouterBridge" "router_bridge.py"
  status_proc "ModelWorker" "workers/model_worker.py"
  status_proc "Agent系统" "start_agent_system.py"
  echo ""
  echo "日志："
  echo "  tail -f logs/router_bridge.log"
  echo "  tail -f logs/model_worker.log"
}

stop_all() {
  echo "🛑 停止 AI PaaS（v2）..."
  stop_proc "Agent系统" "$AGENT_SYSTEM_PID" "start_agent_system.py"
  stop_proc "ModelWorker" "$MODEL_WORKER_PID" "workers/model_worker.py"
  stop_proc "RouterBridge" "$ROUTER_BRIDGE_PID" "router_bridge.py"
  stop_proc "LangGraph服务" "$LANGGRAPH_PID" "langgraph_grpc_server.py"
  stop_proc "Redis消息总线" "$REDIS_BUS_PID" "run_bus.py"
  echo "✅ 全部停止完成"
}

status_all() {
  echo "📊 AI PaaS（v2）状态："
  status_proc "Redis消息总线" "run_bus.py"
  status_proc "LangGraph服务" "langgraph_grpc_server.py"
  status_proc "RouterBridge" "router_bridge.py"
  status_proc "ModelWorker" "workers/model_worker.py"
  status_proc "Agent系统" "start_agent_system.py"
}

run_test() {
  echo "🧪 运行多租户 + ABAC 联调测试..."

  if ! is_running "run_bus.py"; then
    echo "❌ Redis消息总线未运行，请先 start"
    exit 1
  fi
  if ! is_running "router_bridge.py"; then
    echo "❌ RouterBridge未运行，请先 start"
    exit 1
  fi
  if ! is_running "workers/model_worker.py"; then
    echo "❌ ModelWorker未运行，请先 start"
    exit 1
  fi

  cd "$SCRIPT_DIR"
  python tests/test_multitenant_abac_flow.py
}

case "${1:-}" in
  start) start_all ;;
  stop) stop_all ;;
  restart) stop_all; sleep 2; start_all ;;
  status) status_all ;;
  test) run_test ;;
  *)
    echo "用法: $0 {start|stop|restart|status|test}"
    exit 1
    ;;
esac
