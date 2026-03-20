#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run/phase17"
LOG_DIR="${RUN_DIR}/logs"
PID_DIR="${RUN_DIR}/pids"

print_status() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" || true)"

    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[phase17-status] ${name}: RUNNING (pid=${pid})"
    else
      echo "[phase17-status] ${name}: NOT RUNNING (stale pid file: ${pid_file})"
    fi
  else
    echo "[phase17-status] ${name}: NOT STARTED"
  fi

  if [[ -f "$log_file" ]]; then
    echo "[phase17-status] ${name} recent log:"
    tail -n 10 "$log_file" || true
  else
    echo "[phase17-status] ${name} log file missing: ${log_file}"
  fi

  echo "------------------------------------------------------------"
}

echo "[phase17-status] root: ${ROOT_DIR}"
echo "[phase17-status] run dir: ${RUN_DIR}"
echo

print_status "api" "${PID_DIR}/api.pid" "${LOG_DIR}/api.log"
print_status "relay" "${PID_DIR}/relay.pid" "${LOG_DIR}/relay.log"
print_status "agent-worker" "${PID_DIR}/agent-worker.pid" "${LOG_DIR}/agent-worker.log"
print_status "generation-worker" "${PID_DIR}/generation-worker.pid" "${LOG_DIR}/generation-worker.log"