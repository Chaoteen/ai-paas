#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-ops/env/proxy.env}"
DROPIN_DIR="/etc/systemd/system/docker.service.d"
DROPIN_FILE="${DROPIN_DIR}/proxy.conf"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: env file not found: ${ENV_FILE}" >&2
  echo "HINT: cp ops/env/proxy.env.example ops/env/proxy.env && edit it" >&2
  exit 1
fi

# Load env vars (ignore comments/blank lines)
set -a
# shellcheck disable=SC1090
source <(grep -vE '^\s*#' "${ENV_FILE}" | sed '/^\s*$/d')
set +a

# Build systemd drop-in
sudo mkdir -p "${DROPIN_DIR}"

sudo tee "${DROPIN_FILE}" >/dev/null <<EOF
[Service]
Environment="HTTP_PROXY=${HTTP_PROXY:-}"
Environment="HTTPS_PROXY=${HTTPS_PROXY:-}"
Environment="ALL_PROXY=${ALL_PROXY:-}"
Environment="NO_PROXY=${NO_PROXY:-localhost,127.0.0.1,::1}"
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker

echo "OK: docker proxy applied from ${ENV_FILE}"
systemctl show docker --property=Environment --no-pager
