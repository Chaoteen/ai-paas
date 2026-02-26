#!/bin/bash
# start_infra.sh: 启动基础设施 (Ollama, Redis, OPA)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

log_info() { echo -e "\033[0;32m[INFRA]\033[0m $1"; }
log_warn() { echo -e "\033[1;33m[INFRA]\033[0m $1"; }

# --- 1. Ollama (WSL Native) ---
start_ollama() {
  log_info "检查 Ollama..."
  if pgrep -f "ollama serve" > /dev/null; then
    # 检查监听地址是否为 0.0.0.0
    if netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:11434"; then
      log_warn "Ollama 正在运行但只监听 127.0.0.1，正在重启以开放网络..."
      pkill -9 ollama || true
      sleep 2
    else
      log_info "✅ Ollama 已运行且网络正常"
      return 0
    fi
  fi
  
  log_info "🚀 启动 Ollama (OLLAMA_HOST=0.0.0.0)..."
  export OLLAMA_HOST=0.0.0.0
  nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
  sleep 3
  if pgrep -f "ollama serve" > /dev/null; then
    log_info "✅ Ollama 启动成功"
  else
    log_warn "❌ Ollama 启动失败，请检查日志"
  fi
}

# --- 2. Redis (Docker 优先) ---
start_redis() {
  log_info "检查 Redis..."
  if docker ps --format '{{.Names}}' | grep -q "^redis$"; then
    log_info "✅ Redis (Docker) 已运行"
    return 0
  fi
  
  if nc -z localhost 6379 2>/dev/null; then
    log_info "✅ Redis (Native) 已运行"
    return 0
  fi

  log_info "🚀 启动 Redis (Docker)..."
  docker run -d --name redis -p 6379:6379 --restart unless-stopped redis:alpine || log_warn "Redis 启动失败"
}

# --- 3. OPA (Docker) ---
start_opa() {
  log_info "检查 OPA..."
  if docker ps --format '{{.Names}}' | grep -q "^opa$"; then
    log_info "✅ OPA 已运行"
    return 0
  fi

  log_info "🚀 启动 OPA (Docker)..."
  # 先清理可能存在的僵尸容器
  docker rm -f opa 2>/dev/null || true
  
  docker run -d \
    --name opa \
    -p 8181:8181 \
    --restart unless-stopped \
    openpolicyagent/opa:latest \
    run --server --addr 0.0.0.0:8181 --log-level=info || log_warn "OPA 启动失败"
  
  sleep 3
  if curl -s http://127.0.0.1:8181/health >/dev/null; then
    log_info "✅ OPA 健康检查通过"
  else
    log_warn "⚠️ OPA 启动但健康检查未通过"
  fi
}

# --- Main ---
case "${1:-start}" in
  start)
    start_ollama
    start_redis
    start_opa
    ;;
  stop)
    log_info "停止基础设施..."
    docker rm -f opa 2>/dev/null || true
    docker rm -f redis 2>/dev/null || true
    pkill -f "ollama serve" || true
    log_info "✅ 基础设施已停止"
    ;;
  *)
    echo "用法: $0 {start|stop}"
    exit 1
    ;;
esac