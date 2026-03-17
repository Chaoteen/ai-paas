CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS data_events_v2 (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    stream VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    tenant_id VARCHAR(255),
    correlation_id VARCHAR(255),
    task_id VARCHAR(255),
    workflow_id VARCHAR(255),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    retry_count INTEGER NOT NULL DEFAULT 0,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_event_type
    ON data_events_v2(event_type);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_stream
    ON data_events_v2(stream);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_source
    ON data_events_v2(source);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_tenant_id
    ON data_events_v2(tenant_id);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_correlation_id
    ON data_events_v2(correlation_id);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_task_id
    ON data_events_v2(task_id);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_workflow_id
    ON data_events_v2(workflow_id);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_occurred_at
    ON data_events_v2(occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_created_at
    ON data_events_v2(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_payload_gin
    ON data_events_v2 USING GIN (payload);

CREATE INDEX IF NOT EXISTS idx_data_events_v2_headers_gin
    ON data_events_v2 USING GIN (headers);