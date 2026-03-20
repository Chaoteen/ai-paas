#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[DEPRECATED] run_ai_platform_v2.sh 已冻结，不再作为正式版启动入口。"
echo "[DEPRECATED] 正式版唯一总控脚本是: ./run_ai_platform_v4.sh"
echo "[DEPRECATED] 当前将自动转发到 run_ai_platform_v4.sh"

exec "$SCRIPT_DIR/run_ai_platform_v4.sh" "${1:-start}"
