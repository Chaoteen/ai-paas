#!/usr/bin/env bash
# start_frontend.sh: 启动正式主线前端（Vite webapp）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$ROOT_DIR/webapp"

log_info() { echo -e "\033[0;36m[FRONTEND]\033[0m $1"; }
log_warn() { echo -e "\033[1;33m[FRONTEND]\033[0m $1"; }

start_frontend() {
  log_info "正式主线前端: webapp (Vite)"
  log_info "访问地址: http://localhost:5173"

  if [ ! -d "$WEBAPP_DIR" ]; then
    echo "[FRONTEND] webapp 目录不存在: $WEBAPP_DIR"
    exit 1
  fi

  cd "$WEBAPP_DIR"

  if [ ! -d node_modules ]; then
    log_info "node_modules 不存在，执行 npm install ..."
    npm install
  fi

  exec npm run dev -- --host 0.0.0.0 --port 5173
}

stop_frontend() {
  if pgrep -f "vite.*5173" >/dev/null 2>&1; then
    pkill -f "vite.*5173" || true
    log_info "已停止 Vite 前端进程"
  else
    log_warn "未发现运行中的 Vite 前端进程"
  fi
}

case "${1:-start}" in
  start)
    start_frontend
    ;;
  stop)
    stop_frontend
    ;;
  *)
    echo "用法: $0 {start|stop}"
    exit 1
    ;;
esac
