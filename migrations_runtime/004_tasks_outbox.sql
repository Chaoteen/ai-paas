BEGIN;

-- ============================================================================
-- Phase 16F Outbox Hardening
-- - durable task table for async runtime state
-- - durable outbox table for transactional publish relay
-- - indexes for polling, replay, tenant/task lookup
-- ============================================================================

CREATE TABLE IF NOT EXISTS runtime_tasks (
    task_id              VARCHAR(64) PRIMARY KEY,
    tenant_id            VARCHAR(128) NOT NULL,
    task_type            VARCHAR(32) NOT NULL,
    queue_name           VARCHAR(128) NOT NULL,
    status               VARCHAR(32) NOT NULL,

    payload_json         JSONB NOT NULL,
    result_json          JSONB NULL,
    error_text           TEXT NULL,

    retry_count          INTEGER NOT NULL DEFAULT 0,
    correlation_id       VARCHAR(128) NULL,
    idempotency_key      VARCHAR(256) NULL,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    queued_at            TIMESTAMPTZ NULL,
    started_at           TIMESTAMPTZ NULL,
    finished_at          TIMESTAMPTZ NULL,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_runtime_tasks_status
        CHECK (status IN ('created', 'queued', 'running', 'succeeded', 'failed')),

    CONSTRAINT chk_runtime_tasks_task_type
        CHECK (task_type IN ('agent', 'generation'))
);

CREATE INDEX IF NOT EXISTS idx_runtime_tasks_tenant_id
    ON runtime_tasks (tenant_id);

CREATE INDEX IF NOT EXISTS idx_runtime_tasks_status
    ON runtime_tasks (status);

CREATE INDEX IF NOT EXISTS idx_runtime_tasks_queue_name_status
    ON runtime_tasks (queue_name, status);

CREATE INDEX IF NOT EXISTS idx_runtime_tasks_created_at
    ON runtime_tasks (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_runtime_tasks_correlation_id
    ON runtime_tasks (correlation_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_runtime_tasks_tenant_idempotency_key
    ON runtime_tasks (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;


CREATE TABLE IF NOT EXISTS runtime_outbox_events (
    event_id             BIGSERIAL PRIMARY KEY,

    aggregate_type       VARCHAR(64) NOT NULL,
    aggregate_id         VARCHAR(64) NOT NULL,
    tenant_id            VARCHAR(128) NOT NULL,

    event_type           VARCHAR(64) NOT NULL,
    queue_name           VARCHAR(128) NOT NULL,
    stream_name          VARCHAR(128) NOT NULL,

    payload_json         JSONB NOT NULL,

    status               VARCHAR(32) NOT NULL DEFAULT 'pending',
    publish_attempts     INTEGER NOT NULL DEFAULT 0,
    last_error_text      TEXT NULL,

    available_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at         TIMESTAMPTZ NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_runtime_outbox_status
        CHECK (status IN ('pending', 'publishing', 'published', 'failed')),

    CONSTRAINT chk_runtime_outbox_aggregate_type
        CHECK (aggregate_type IN ('task')),

    CONSTRAINT chk_runtime_outbox_event_type
        CHECK (event_type IN ('task.queued'))
);

CREATE INDEX IF NOT EXISTS idx_runtime_outbox_status_available_at
    ON runtime_outbox_events (status, available_at, event_id);

CREATE INDEX IF NOT EXISTS idx_runtime_outbox_aggregate_id
    ON runtime_outbox_events (aggregate_id);

CREATE INDEX IF NOT EXISTS idx_runtime_outbox_tenant_id
    ON runtime_outbox_events (tenant_id);

CREATE INDEX IF NOT EXISTS idx_runtime_outbox_created_at
    ON runtime_outbox_events (created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_runtime_outbox_task_queued_once
    ON runtime_outbox_events (aggregate_type, aggregate_id, event_type);


-- Optional helper trigger for updated_at. If your repo already has a shared
-- trigger function, you can replace this block with that shared function.
CREATE OR REPLACE FUNCTION set_runtime_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_runtime_tasks_updated_at ON runtime_tasks;
CREATE TRIGGER trg_runtime_tasks_updated_at
BEFORE UPDATE ON runtime_tasks
FOR EACH ROW
EXECUTE FUNCTION set_runtime_updated_at();

DROP TRIGGER IF EXISTS trg_runtime_outbox_events_updated_at ON runtime_outbox_events;
CREATE TRIGGER trg_runtime_outbox_events_updated_at
BEFORE UPDATE ON runtime_outbox_events
FOR EACH ROW
EXECUTE FUNCTION set_runtime_updated_at();

COMMIT;