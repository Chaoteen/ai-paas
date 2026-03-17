CREATE TABLE IF NOT EXISTS data_events (
    id TEXT PRIMARY KEY,
    event_id TEXT,
    event_type VARCHAR(100) NOT NULL,
    stream VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    tenant_id VARCHAR(255),
    correlation_id VARCHAR(255),
    task_id VARCHAR(255),
    workflow_id VARCHAR(255),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    retry_count INTEGER NOT NULL DEFAULT 0,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE data_events ADD COLUMN IF NOT EXISTS event_id TEXT;
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS stream VARCHAR(100);
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS source VARCHAR(100);
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255);
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(255);
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS task_id VARCHAR(255);
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS workflow_id VARCHAR(255);
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20) NOT NULL DEFAULT '1.0';
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE data_events ADD COLUMN IF NOT EXISTS headers JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_data_events_event_type ON data_events(event_type);
CREATE INDEX IF NOT EXISTS idx_data_events_task_id ON data_events(task_id);
CREATE INDEX IF NOT EXISTS idx_data_events_workflow_id ON data_events(workflow_id);
CREATE INDEX IF NOT EXISTS idx_data_events_tenant_id ON data_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_events_occurred_at ON data_events(occurred_at DESC);