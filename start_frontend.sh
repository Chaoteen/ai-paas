#!/bin/bash
# start_frontend.sh: 启动独立前端 (如有)
set -euo pipefail

log_info() { echo -e "\033[0;36m[FRONTEND]\033[0m $1"; }

case "${1:-start}" in
  start)
    log_info "ℹ️  当前前端由 Flowise (Docker) 提供，无需额外启动。"
    log_info "🌐 访问地址: http://localhost:3000"
    ;;
  stop)
    log_info "ℹ️  无独立前端进程需要停止。"
    ;;
  *)
    echo "用法: $0 {start|stop}"
    ;;
esac