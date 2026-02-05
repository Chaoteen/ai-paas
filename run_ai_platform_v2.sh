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
PROMPTFLOW_PID="$PID_DIR/promptflow.pid"

# --- ENV（可按需改）---
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
export SOURCE_STREAM="${SOURCE_STREAM:-agent.tasks.stream}"
export SOURCE_GROUP="${SOURCE_GROUP:-router_workers}"
export DEST_STREAM="${DEST_STREAM:-agent.processed.tasks.stream}"
export RESULT_STREAM="${RESULT_STREAM:-agent.result.stream}"

export LANGGRAPH_SERVICE_URL="${LANGGRAPH_SERVICE_URL:-localhost:50051}"
# promptflow (iframe target)
export PROMPTFLOW_PORT="${PROMPTFLOW_PORT:-8080}"
export PROMPTFLOW_SERVICE_URL="${PROMPTFLOW_SERVICE_URL:-http://127.0.0.1:${PROMPTFLOW_PORT}}"
# Optional: if no docker-compose detected, use PROMPTFLOW_CMD to start promptflow process
export PROMPTFLOW_CMD="${PROMPTFLOW_CMD:-}"
# model worker
export MODEL_WORKER_GROUP="${MODEL_WORKER_GROUP:-model_workers}"
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
export DEFAULT_MODEL_ID="${DEFAULT_MODEL_ID:-deepseek-r1:latest}"

# --- helpers ---
is_running() { pgrep -f "$1" >/dev/null 2>&1; }

wait_http() {
  # wait_http <url> <timeout_seconds>
  local url="$1"
  local timeout="${2:-20}"
  local i=0
  while (( i < timeout )); do
    if curl -sS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i+1))
  done
  return 1
}


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

start_promptflow() {
  echo "=== 2.5) PromptFlow（iframe 插件） ==="

  # Preferred: docker compose if present
  local compose1="$SCRIPT_DIR/ops/promptflow/docker-compose.yml"
  local compose2="$SCRIPT_DIR/promptflow/docker-compose.yml"

  if [[ -f "$compose1" ]]; then
    echo "🚀 启动 PromptFlow (docker compose: ops/promptflow) ..."
    (cd "$(dirname "$compose1")" && docker compose up -d)
  elif [[ -f "$compose2" ]]; then
    echo "🚀 启动 PromptFlow (docker compose: promptflow) ..."
    (cd "$(dirname "$compose2")" && docker compose up -d)
  elif [[ -n "${PROMPTFLOW_CMD:-}" ]]; then
    start_proc \
      "PromptFlow服务" \
      "$SCRIPT_DIR" \
      "$PROMPTFLOW_CMD" \
      "$PROMPTFLOW_PID" \
      "$LOG_DIR/promptflow.log" \
      "$PROMPTFLOW_CMD" \
      3 || true
  else
    echo "⚠️ 未找到 PromptFlow docker-compose.yml，且未设置 PROMPTFLOW_CMD，跳过启动 PromptFlow"
    echo "   你可以："
    echo "   1) 放置 docker compose 文件到 ops/promptflow/docker-compose.yml 或 promptflow/docker-compose.yml"
    echo "   2) 或 export PROMPTFLOW_CMD='你的启动命令' 让脚本托管进程"
    return 0
  fi

  # Health check
  if wait_http "http://127.0.0.1:${PROMPTFLOW_PORT}/swagger.json" 20; then
    echo "✅ PromptFlow 已就绪: http://127.0.0.1:${PROMPTFLOW_PORT}"
  else
    echo "❌ PromptFlow 未就绪（端口 ${PROMPTFLOW_PORT} 20秒内不可达）"
    echo "   建议查看：logs/promptflow.log 或 docker logs"
  fi
}

stop_promptflow() {
  echo "🛑 停止 PromptFlow ..."
  local compose1="$SCRIPT_DIR/ops/promptflow/docker-compose.yml"
  local compose2="$SCRIPT_DIR/promptflow/docker-compose.yml"

  if [[ -f "$compose1" ]]; then
    (cd "$(dirname "$compose1")" && docker compose down) || true
    echo "✅ PromptFlow docker compose 已停止"
    return 0
  fi
  if [[ -f "$compose2" ]]; then
    (cd "$(dirname "$compose2")" && docker compose down) || true
    echo "✅ PromptFlow docker compose 已停止"
    return 0
  fi

  # If started as process
  stop_proc "PromptFlow服务" "$PROMPTFLOW_PID" "${PROMPTFLOW_CMD:-promptflow}"
}

status_promptflow() {
  if curl -sS "http://127.0.0.1:${PROMPTFLOW_PORT}/swagger.json" >/dev/null 2>&1; then
    echo "✅ PromptFlow 正在运行 (http://127.0.0.1:${PROMPTFLOW_PORT})"
  else
    echo "❌ PromptFlow 未运行 (http://127.0.0.1:${PROMPTFLOW_PORT} 不可达)"
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

  start_promptflow

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
  status_promptflow
  status_promptflow
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
  status_promptflow
  status_promptflow
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
