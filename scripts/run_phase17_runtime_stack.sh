#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FOLLOW_LOGS=0

usage() {
  cat <<'EOF'
Usage:
  bash ./scripts/run_phase17_runtime_stack.sh [--follow]

Options:
  --follow   Follow runtime logs in foreground after startup
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --follow)
      FOLLOW_LOGS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[phase17] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "[phase17] required environment variable is missing: $name" >&2
    exit 1
  fi
}

require_env POSTGRES_HOST
require_env POSTGRES_PORT
require_env POSTGRES_DB
require_env POSTGRES_USER
require_env POSTGRES_PASSWORD
require_env REDIS_URL

export TASK_STORE_BACKEND="${TASK_STORE_BACKEND:-postgres}"
API_PORT="${API_PORT:-8000}"
API_HOST="${API_HOST:-0.0.0.0}"

RUN_DIR="${ROOT_DIR}/.run/phase17"
LOG_DIR="${RUN_DIR}/logs"
PID_DIR="${RUN_DIR}/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

API_LOG="${LOG_DIR}/api.log"
RELAY_LOG="${LOG_DIR}/relay.log"
AGENT_WORKER_LOG="${LOG_DIR}/agent-worker.log"
GEN_WORKER_LOG="${LOG_DIR}/generation-worker.log"

API_PID_FILE="${PID_DIR}/api.pid"
RELAY_PID_FILE="${PID_DIR}/relay.pid"
AGENT_PID_FILE="${PID_DIR}/agent-worker.pid"
GEN_PID_FILE="${PID_DIR}/generation-worker.pid"

touch "$API_LOG" "$RELAY_LOG" "$AGENT_WORKER_LOG" "$GEN_WORKER_LOG"

is_pid_running() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null
}

ensure_not_running() {
  local name="$1"
  local pid_file="$2"
  if is_pid_running "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"
    echo "[phase17] ${name} is already running with pid ${pid}. Stop it first." >&2
    exit 1
  fi
  rm -f "$pid_file"
}

wait_for_pid_alive() {
  local pid_file="$1"
  local name="$2"
  local retries="${3:-20}"
  local sleep_seconds="${4:-0.2}"

  local pid
  pid="$(cat "$pid_file")"

  for ((i=1; i<=retries; i++)); do
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "[phase17] ${name} failed to stay alive after startup. Check logs." >&2
  exit 1
}

echo "[phase17] root dir: $ROOT_DIR"
echo "[phase17] postgres: ${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "[phase17] redis: ${REDIS_URL}"
echo "[phase17] api: http://${API_HOST}:${API_PORT}"
echo "[phase17] logs: ${LOG_DIR}"
echo

ensure_not_running "api" "$API_PID_FILE"
ensure_not_running "relay" "$RELAY_PID_FILE"
ensure_not_running "agent worker" "$AGENT_PID_FILE"
ensure_not_running "generation worker" "$GEN_PID_FILE"

echo "[phase17] running preflight gate..."
bash "${ROOT_DIR}/scripts/check_phase17_runtime_ready.sh"
echo "[phase17] preflight passed"
echo

echo "[phase17] starting API..."
nohup env \
  TASK_STORE_BACKEND="$TASK_STORE_BACKEND" \
  POSTGRES_HOST="$POSTGRES_HOST" \
  POSTGRES_PORT="$POSTGRES_PORT" \
  POSTGRES_DB="$POSTGRES_DB" \
  POSTGRES_USER="$POSTGRES_USER" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  REDIS_URL="$REDIS_URL" \
  uvicorn gateway.main:app --host "$API_HOST" --port "$API_PORT" \
  >"$API_LOG" 2>&1 &
echo $! > "$API_PID_FILE"
wait_for_pid_alive "$API_PID_FILE" "api"

echo "[phase17] starting outbox relay..."
nohup env \
  POSTGRES_HOST="$POSTGRES_HOST" \
  POSTGRES_PORT="$POSTGRES_PORT" \
  POSTGRES_DB="$POSTGRES_DB" \
  POSTGRES_USER="$POSTGRES_USER" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  REDIS_URL="$REDIS_URL" \
  python -m bootstrap.outbox_relay_runner \
  >"$RELAY_LOG" 2>&1 &
echo $! > "$RELAY_PID_FILE"
wait_for_pid_alive "$RELAY_PID_FILE" "relay"

echo "[phase17] starting agent worker..."
nohup env \
  TASK_STORE_BACKEND="$TASK_STORE_BACKEND" \
  POSTGRES_HOST="$POSTGRES_HOST" \
  POSTGRES_PORT="$POSTGRES_PORT" \
  POSTGRES_DB="$POSTGRES_DB" \
  POSTGRES_USER="$POSTGRES_USER" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  REDIS_URL="$REDIS_URL" \
  AI_PAAS_WORKER_KIND="agent" \
  AI_PAAS_WORKER_CONSUMER_NAME="agent-worker-1" \
  python -m bootstrap.runtime_worker_runner \
  >"$AGENT_WORKER_LOG" 2>&1 &
echo $! > "$AGENT_PID_FILE"
wait_for_pid_alive "$AGENT_PID_FILE" "agent worker"

echo "[phase17] starting generation worker..."
nohup env \
  TASK_STORE_BACKEND="$TASK_STORE_BACKEND" \
  POSTGRES_HOST="$POSTGRES_HOST" \
  POSTGRES_PORT="$POSTGRES_PORT" \
  POSTGRES_DB="$POSTGRES_DB" \
  POSTGRES_USER="$POSTGRES_USER" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  REDIS_URL="$REDIS_URL" \
  AI_PAAS_WORKER_KIND="generation" \
  AI_PAAS_WORKER_CONSUMER_NAME="generation-worker-1" \
  python -m bootstrap.runtime_worker_runner \
  >"$GEN_WORKER_LOG" 2>&1 &
echo $! > "$GEN_PID_FILE"
wait_for_pid_alive "$GEN_PID_FILE" "generation worker"

echo "[phase17] startup complete"
echo "[phase17] pid files:"
echo "  api: $(cat "$API_PID_FILE")"
echo "  relay: $(cat "$RELAY_PID_FILE")"
echo "  agent worker: $(cat "$AGENT_PID_FILE")"
echo "  generation worker: $(cat "$GEN_PID_FILE")"
echo

echo "[phase17] recent logs:"
echo "------------------------------------------------------------"
tail -n 20 "$API_LOG" || true
tail -n 20 "$RELAY_LOG" || true
tail -n 20 "$AGENT_WORKER_LOG" || true
tail -n 20 "$GEN_WORKER_LOG" || true
echo "------------------------------------------------------------"

if [[ "$FOLLOW_LOGS" == "1" ]]; then
  echo
  echo "[phase17] following logs... press Ctrl+C to stop log streaming"
  tail -f "$API_LOG" "$RELAY_LOG" "$AGENT_WORKER_LOG" "$GEN_WORKER_LOG"
else
  echo
  echo "[phase17] startup finished. Logs are in ${LOG_DIR}"
  echo "[phase17] use --follow if you want foreground log streaming"
fi