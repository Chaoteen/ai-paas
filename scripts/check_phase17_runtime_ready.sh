#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python - <<'PY'
from __future__ import annotations

import asyncio
import json
import sys

from runtime.preflight import collect_runtime_preflight

async def main() -> int:
    report = await collect_runtime_preflight()
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report.get("ok", False):
        return 0

    return 1

raise SystemExit(asyncio.run(main()))
PY