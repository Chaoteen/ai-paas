#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_DIR="${ROOT_DIR}/.run/phase17"
LOG_DIR="${RUN_DIR}/logs"
PID_DIR="${RUN_DIR}/pids"

API_PID_FILE="${PID_DIR}/api.pid"
RELAY_PID_FILE="${PID_DIR}/relay.pid"
AGENT_PID_FILE="${PID_DIR}/agent-worker.pid"
GEN_PID_FILE="${PID_DIR}/generation-worker.pid"

API_LOG="${LOG_DIR}/api.log"
RELAY_LOG="${LOG_DIR}/relay.log"
AGENT_WORKER_LOG="${LOG_DIR}/agent-worker.log"
GEN_WORKER_LOG="${LOG_DIR}/generation-worker.log"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
HEALTH_URL="http://${API_HOST}:${API_PORT}/api/health"

print_header() {
  echo "[phase17-status] root dir: ${ROOT_DIR}"
  echo "[phase17-status] run dir: ${RUN_DIR}"
  echo "[phase17-status] health url: ${HEALTH_URL}"
  echo
}

pid_value() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    cat "$pid_file" 2>/dev/null || true
  fi
}

print_process_status() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    printf "%-20s %s\n" "${name}:" "missing pid file"
    return 0
  fi

  local pid
  pid="$(pid_value "$pid_file")"

  if [[ -z "${pid:-}" ]]; then
    printf "%-20s %s\n" "${name}:" "pid file empty"
    return 0
  fi

  if kill -0 "$pid" 2>/dev/null; then
    printf "%-20s %s\n" "${name}:" "running (pid=${pid})"
  else
    printf "%-20s %s\n" "${name}:" "stale pid file (pid=${pid})"
  fi
}

fetch_health() {
  python - <<'PY'
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

url = os.environ["PHASE17_HEALTH_URL"]

try:
    req = Request(url=url, method="GET")
    with urlopen(req, timeout=3) as response:
        body = response.read().decode("utf-8")
        data = json.loads(body)
        print(json.dumps({
            "reachable": True,
            "status_code": response.status,
            "body": data,
        }, ensure_ascii=False))
except HTTPError as exc:
    try:
        body = exc.read().decode("utf-8")
        data = json.loads(body)
    except Exception:
        data = {"raw": ""}
    print(json.dumps({
        "reachable": True,
        "status_code": exc.code,
        "body": data,
    }, ensure_ascii=False))
except (URLError, TimeoutError, OSError) as exc:
    print(json.dumps({
        "reachable": False,
        "error": str(exc),
    }, ensure_ascii=False))
PY
}

print_health_status() {
  local result
  result="$(PHASE17_HEALTH_URL="$HEALTH_URL" fetch_health)"

  python - "$result" <<'PY'
from __future__ import annotations

import json
import sys

payload = json.loads(sys.argv[1])

print("health api:")

if not payload.get("reachable", False):
    print("  reachable: no")
    print(f"  error: {payload.get('error', '')}")
    raise SystemExit(0)

status_code = payload.get("status_code")
body = payload.get("body", {})
ok = body.get("ok")

print("  reachable: yes")
print(f"  status_code: {status_code}")
print(f"  ok: {ok}")

components = body.get("components")
if isinstance(components, dict):
    for name in ("postgres", "redis", "runtime_schema"):
        component = components.get(name, {})
        if component:
            print(f"  {name}: ok={component.get('ok')}")
            if component.get("error"):
                print(f"    error: {component.get('error')}")
PY
}

print_preflight_status() {
  echo "preflight gate:"
  if bash "${ROOT_DIR}/scripts/check_phase17_runtime_ready.sh" >/tmp/phase17_preflight_status.json 2>/tmp/phase17_preflight_status.err; then
    echo "  exit_code: 0"
    echo "  status: passed"
    sed 's/^/  /' /tmp/phase17_preflight_status.json
  else
    local exit_code=$?
    echo "  exit_code: ${exit_code}"
    echo "  status: failed"
    if [[ -s /tmp/phase17_preflight_status.json ]]; then
      sed 's/^/  /' /tmp/phase17_preflight_status.json
    fi
    if [[ -s /tmp/phase17_preflight_status.err ]]; then
      sed 's/^/  /' /tmp/phase17_preflight_status.err
    fi
  fi
  rm -f /tmp/phase17_preflight_status.json /tmp/phase17_preflight_status.err
}

print_recent_logs() {
  echo
  echo "recent logs:"
  echo "------------------------------------------------------------"

  for log_file in \
    "$API_LOG" \
    "$RELAY_LOG" \
    "$AGENT_WORKER_LOG" \
    "$GEN_WORKER_LOG"
  do
    echo "==> ${log_file}"
    if [[ -f "$log_file" ]]; then
      tail -n 10 "$log_file" || true
    else
      echo "(missing)"
    fi
    echo
  done

  echo "------------------------------------------------------------"
}

main() {
  print_header

  echo "processes:"
  print_process_status "api" "$API_PID_FILE"
  print_process_status "relay" "$RELAY_PID_FILE"
  print_process_status "agent worker" "$AGENT_PID_FILE"
  print_process_status "generation worker" "$GEN_PID_FILE"
  echo

  print_health_status
  echo

  print_preflight_status

  print_recent_logs
}

main "$@"
