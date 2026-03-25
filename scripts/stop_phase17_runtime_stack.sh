#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_DIR="${ROOT_DIR}/.run/phase17"
PID_DIR="${RUN_DIR}/pids"

API_PID_FILE="${PID_DIR}/api.pid"
RELAY_PID_FILE="${PID_DIR}/relay.pid"
AGENT_PID_FILE="${PID_DIR}/agent-worker.pid"
GEN_PID_FILE="${PID_DIR}/generation-worker.pid"

STOP_FAILURES=0

pid_value() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    cat "$pid_file" 2>/dev/null || true
  fi
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null
}

wait_for_pid_exit() {
  local pid="$1"
  local name="$2"
  local retries="${3:-30}"
  local sleep_seconds="${4:-0.2}"

  for ((i=1; i<=retries; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "[phase17-stop] ${name} did not exit in time (pid=${pid})" >&2
  return 1
}

stop_one() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "[phase17-stop] ${name}: pid file missing"
    return 0
  fi

  local pid
  pid="$(pid_value "$pid_file")"

  if [[ -z "${pid:-}" ]]; then
    echo "[phase17-stop] ${name}: pid file empty, removing"
    rm -f "$pid_file"
    return 0
  fi

  if ! is_pid_running "$pid"; then
    echo "[phase17-stop] ${name}: stale pid file (pid=${pid}), removing"
    rm -f "$pid_file"
    return 0
  fi

  echo "[phase17-stop] ${name}: stopping pid ${pid}"
  kill "$pid" 2>/dev/null || true

  if wait_for_pid_exit "$pid" "$name"; then
    echo "[phase17-stop] ${name}: stopped"
    rm -f "$pid_file"
    return 0
  fi

  echo "[phase17-stop] ${name}: sending SIGKILL to pid ${pid}"
  kill -9 "$pid" 2>/dev/null || true

  if wait_for_pid_exit "$pid" "$name" 10 0.2; then
    echo "[phase17-stop] ${name}: killed"
    rm -f "$pid_file"
    return 0
  fi

  echo "[phase17-stop] ${name}: failed to stop pid ${pid}" >&2
  STOP_FAILURES=$((STOP_FAILURES + 1))
  return 1
}

main() {
  mkdir -p "$PID_DIR"

  echo "[phase17-stop] root dir: ${ROOT_DIR}"
  echo "[phase17-stop] pid dir: ${PID_DIR}"
  echo

  stop_one "generation worker" "$GEN_PID_FILE" || true
  stop_one "agent worker" "$AGENT_PID_FILE" || true
  stop_one "relay" "$RELAY_PID_FILE" || true
  stop_one "api" "$API_PID_FILE" || true

  echo
  if [[ "$STOP_FAILURES" -eq 0 ]]; then
    echo "[phase17-stop] done"
    exit 0
  fi

  echo "[phase17-stop] completed with ${STOP_FAILURES} failure(s)" >&2
  exit 1
}

main "$@"