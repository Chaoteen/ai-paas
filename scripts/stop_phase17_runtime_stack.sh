#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run/phase17"
PID_DIR="${RUN_DIR}/pids"

if [[ ! -d "$PID_DIR" ]]; then
  echo "[phase17-stop] no pid directory found: $PID_DIR"
  exit 0
fi

stop_pid_file() {
  local pid_file="$1"

  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" || true)"

  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "[phase17-stop] stopping pid $pid from $(basename "$pid_file")"
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  else
    echo "[phase17-stop] pid file exists but process not running: $(basename "$pid_file")"
  fi

  rm -f "$pid_file"
}

stop_pid_file "${PID_DIR}/generation-worker.pid"
stop_pid_file "${PID_DIR}/agent-worker.pid"
stop_pid_file "${PID_DIR}/relay.pid"
stop_pid_file "${PID_DIR}/api.pid"

echo "[phase17-stop] done"