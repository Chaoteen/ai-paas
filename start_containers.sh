#!/bin/bash
# start_containers.sh: 启动 Docker 组件 (DB, PromptFlow, Flowise)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

log_info() { echo -e "\033[0;34m[CONTAINERS]\033[0m $1"; }

# 辅助函数：等待端口
wait_port() {
  local port=$1; local timeout=${2:-30}
  for i in $(seq 1 $timeout); do
    if curl -s --connect-timeout 1 "http://127.0.0.1:$port" >/dev/null 2>&1 || nc -z 127.0.0.1 "$port" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# --- 1. PostgreSQL (如果未运行) ---
start_db() {
  log_info "检查 PostgreSQL..."
  
  # --- 策略：优先尝试原生连接，失败再尝试启动服务 ---
  # 完全跳过 docker ps 检查，避免 Docker 假死导致脚本卡住
  
  DB_USER="postgres"
  DB_PASS="postgres"
  DB_NAME="ai_paas"
  DB_HOST="localhost"
  DB_PORT="5432"
  
  # 1. 快速测试连接 (使用 bash 内置 tcp 检测 + psql)
  if (echo >/dev/tcp/$DB_HOST/$DB_PORT) 2>/dev/null; then
    log_info "   端口 $DB_PORT 已开放，测试连接..."
    if PGPASSWORD=$DB_PASS timeout 5 psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" >/dev/null 2>&1; then
      log_info "✅ PostgreSQL (Native) 连接成功 (库: $DB_NAME)"
      return 0
    else
      log_warn "⚠️ 端口开放但连接失败，检查用户/密码/权限"
    fi
  fi

  # 2. 如果连接失败，尝试启动原生服务
  log_info "🚀 尝试启动原生 PostgreSQL 服务..."
  if sudo service postgresql start 2>/dev/null; then
    log_info "   服务启动命令执行完毕"
  elif sudo pg_ctlcluster 15 main start 2>/dev/null; then
    log_info "   pg_ctlcluster 启动完毕"
  else
    log_warn "   自动启动命令未生效或需要手动干预"
  fi
  
  sleep 3
  
  # 3. 再次验证
  if (echo >/dev/tcp/$DB_HOST/$DB_PORT) 2>/dev/null && \
     PGPASSWORD=$DB_PASS timeout 5 psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" >/dev/null 2>&1; then
    log_info "✅ PostgreSQL (Native) 已启动并连接成功"
    return 0
  fi

  log_error "❌ PostgreSQL 无法连接。请手动检查: service postgresql status"
  return 1
}

# --- 2. PromptFlow ---
start_promptflow() {
  log_info "检查 PromptFlow..."
  if docker ps --format '{{.Names}}' | grep -qi "promptflow"; then
    log_info "✅ PromptFlow 已运行"
    return 0
  fi

  local pf_compose="$SCRIPT_DIR/ops/promptflow/docker-compose.yml"
  if [[ -f "$pf_compose" ]]; then
    log_info "🚀 启动 PromptFlow (Compose)..."
    (cd "$(dirname "$pf_compose")" && docker compose up -d)
    if wait_port 8080 20; then log_info "✅ PromptFlow 就绪"; else log_info "⚠️ PromptFlow 启动慢"; fi
  else
    log_info "⚠️ 未找到 PromptFlow compose 文件，跳过"
  fi
}

# --- 3. Flowise ---
start_flowise() {
  log_info "检查 Flowise..."
  if docker ps --format '{{.Names}}' | grep -qi "flowise"; then
    log_info "✅ Flowise 已运行"
    return 0
  fi

  local fw_compose="$SCRIPT_DIR/ops/flowise/docker-compose.yml"
  if [[ -f "$fw_compose" ]]; then
    log_info "🚀 启动 Flowise (Compose)..."
    (cd "$(dirname "$fw_compose")" && docker compose up -d)
    if wait_port 3000 30; then log_info "✅ Flowise 就绪"; else log_info "⚠️ Flowise 启动慢"; fi
  else
    log_info "⚠️ 未找到 Flowise compose 文件，跳过"
  fi
}

# --- Main ---
case "${1:-start}" in
  start)
    start_db
    start_promptflow
    start_flowise
    ;;
  stop)
    log_info "停止 Docker 应用..."
    docker compose -p promptflow down 2>/dev/null || true
    docker compose -p flowise down 2>/dev/null || true
    # 不自动停 DB，防止数据丢失，除非明确指定
    log_info "✅ 应用容器已停止 (DB 保留)"
    ;;
  restart)
    $0 stop
    sleep 2
    $0 start
    ;;
  *)
    echo "用法: $0 {start|stop|restart}"
    exit 1
    ;;
esac