CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(64) NOT NULL,
    status VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(128) NULL,
    capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    heartbeat_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_status ON agents(tenant_id, status);


CREATE TABLE IF NOT EXISTS control_events (
    id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(128) NOT NULL,
    agent_id VARCHAR(64) NULL,
    tenant_id VARCHAR(128) NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_control_events_type ON control_events(event_type);
CREATE INDEX IF NOT EXISTS idx_control_events_agent_id ON control_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_control_events_tenant_id ON control_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_control_events_type_time ON control_events(event_type, occurred_at);


CREATE TABLE IF NOT EXISTS data_events (
    id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(128) NULL,
    execution_id VARCHAR(128) NULL,
    event_type VARCHAR(128) NOT NULL,
    tenant_id VARCHAR(128) NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_events_task_id ON data_events(task_id);
CREATE INDEX IF NOT EXISTS idx_data_events_execution_id ON data_events(execution_id);
CREATE INDEX IF NOT EXISTS idx_data_events_event_type ON data_events(event_type);
CREATE INDEX IF NOT EXISTS idx_data_events_tenant_id ON data_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_events_type_time ON data_events(event_type, occurred_at);