#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export TASK_STORE_BACKEND="${TASK_STORE_BACKEND:-postgres}"
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-ai_paas}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379}"

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

cleanup() {
  echo
  echo "[phase17] stopping runtime stack..."

  for pid_file in "$GEN_PID_FILE" "$AGENT_PID_FILE" "$RELAY_PID_FILE" "$API_PID_FILE"; do
    if [[ -f "$pid_file" ]]; then
      pid="$(cat "$pid_file" || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
      fi
      rm -f "$pid_file"
    fi
  done
}

trap cleanup EXIT INT TERM

echo "[phase17] root dir: $ROOT_DIR"
echo "[phase17] postgres: ${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "[phase17] redis: ${REDIS_URL}"
echo "[phase17] api: http://${API_HOST}:${API_PORT}"
echo "[phase17] logs: ${LOG_DIR}"
echo

echo "[phase17] starting API..."
nohup env \
  TASK_STORE_BACKEND="$TASK_STORE_BACKEND" \
  POSTGRES_HOST="$POSTGRES_HOST" \
  POSTGRES_PORT="$POSTGRES_PORT" \
  POSTGRES_DB="$POSTGRES_DB" \
  POSTGRES_USER="$POSTGRES_USER" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  uvicorn gateway.main:app --host "$API_HOST" --port "$API_PORT" \
  >"$API_LOG" 2>&1 &
echo $! > "$API_PID_FILE"

sleep 2

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

sleep 2

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

sleep 2

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

sleep 2

echo "[phase17] startup complete"
echo "[phase17] pid files:"
echo "  api:              $(cat "$API_PID_FILE")"
echo "  relay:            $(cat "$RELAY_PID_FILE")"
echo "  agent worker:     $(cat "$AGENT_PID_FILE")"
echo "  generation worker:$(cat "$GEN_PID_FILE")"
echo
echo "[phase17] recent logs:"
echo "------------------------------------------------------------"
tail -n 20 "$API_LOG" || true
tail -n 20 "$RELAY_LOG" || true
tail -n 20 "$AGENT_WORKER_LOG" || true
tail -n 20 "$GEN_WORKER_LOG" || true
echo "------------------------------------------------------------"
echo
echo "[phase17] following logs... press Ctrl+C to stop all"
tail -f "$API_LOG" "$RELAY_LOG" "$AGENT_WORKER_LOG" "$GEN_WORKER_LOG"