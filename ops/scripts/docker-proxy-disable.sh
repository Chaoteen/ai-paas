#!/usr/bin/env bash
set -euo pipefail

DROPIN_FILE="/etc/systemd/system/docker.service.d/proxy.conf"

if [[ -f "${DROPIN_FILE}" ]]; then
  sudo rm -f "${DROPIN_FILE}"
  echo "OK: removed ${DROPIN_FILE}"
else
  echo "OK: no ${DROPIN_FILE} (already disabled)"
fi

sudo systemctl daemon-reload
sudo systemctl restart docker

echo "OK: docker proxy disabled"
systemctl show docker --property=Environment --no-pager
