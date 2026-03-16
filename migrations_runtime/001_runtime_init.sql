CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    version VARCHAR NOT NULL DEFAULT '1.0.0',
    status VARCHAR NOT NULL DEFAULT 'active',
    tenant_id VARCHAR,
    capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);


CREATE TABLE IF NOT EXISTS control_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR,
    event_type VARCHAR NOT NULL,
    stream VARCHAR NOT NULL DEFAULT 'control.events',
    source VARCHAR NOT NULL DEFAULT 'control_plane',
    tenant_id VARCHAR,
    correlation_id VARCHAR,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version VARCHAR NOT NULL DEFAULT '1.0'
);

CREATE INDEX IF NOT EXISTS idx_control_events_event_type ON control_events(event_type);
CREATE INDEX IF NOT EXISTS idx_control_events_tenant_id ON control_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_control_events_occurred_at ON control_events(occurred_at DESC);


CREATE TABLE IF NOT EXISTS data_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR,
    event_type VARCHAR NOT NULL,
    stream VARCHAR NOT NULL DEFAULT 'data.events',
    source VARCHAR NOT NULL DEFAULT 'data_plane',
    tenant_id VARCHAR,
    correlation_id VARCHAR,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version VARCHAR NOT NULL DEFAULT '1.0'
);

CREATE INDEX IF NOT EXISTS idx_data_events_event_type ON data_events(event_type);
CREATE INDEX IF NOT EXISTS idx_data_events_tenant_id ON data_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_events_occurred_at ON data_events(occurred_at DESC);
