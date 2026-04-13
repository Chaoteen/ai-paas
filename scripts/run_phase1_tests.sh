#!/usr/bin/env bash
set -euo pipefail

mkdir -p .run/phase1
LOG_FILE=".run/phase1/phase1_tests_$(date +%Y%m%d_%H%M%S).log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Phase1 test run started at $(date) ==="

PGPASSWORD=postgres psql -h 127.0.0.1 -p 5432 -U postgres -d ai_paas -c "TRUNCATE TABLE skill_drafts, recording_action_events, recording_sessions RESTART IDENTITY CASCADE;"

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
POSTGRES_DB=ai_paas \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_paas' \
pytest tests/gateway/test_skill_distillation_api.py -q

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
POSTGRES_DB=ai_paas \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_paas' \
pytest tests/gateway/test_skill_distillation_dialogue_api.py -q

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
POSTGRES_DB=ai_paas \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_paas' \
pytest tests/integration/test_skill_distillation_minimal_flow.py -q

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
POSTGRES_DB=ai_paas \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_paas' \
pytest tests/integration/test_skill_distillation_dialogue_flow.py -q

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
POSTGRES_DB=ai_paas \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_paas' \
pytest tests/integration/test_skill_distillation_postgres_repositories.py -q

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
POSTGRES_DB=ai_paas \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_paas' \
pytest tests/integration/test_skill_distillation_postgres_dialogue_flow.py -q

echo "=== Phase1 test run finished at $(date) ==="
echo "log file: $LOG_FILE"