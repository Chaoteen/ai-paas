BEGIN;

CREATE TABLE IF NOT EXISTS workflow_definitions (
    workflow_key TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    schema_json JSONB NOT NULL,
    input_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    policies_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    governance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum TEXT NULL,
    created_by TEXT NULL,
    updated_by TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workflow_key, workflow_version)
);

CREATE INDEX IF NOT EXISTS idx_workflow_definitions_status
    ON workflow_definitions (status);

CREATE INDEX IF NOT EXISTS idx_workflow_definitions_created_at
    ON workflow_definitions (created_at);


CREATE TABLE IF NOT EXISTS workflow_executions (
    workflow_execution_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    workflow_key TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    status TEXT NOT NULL,
    definition_snapshot_json JSONB NOT NULL,
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    system_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NULL,
    error_text TEXT NULL,
    active_node_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    resolved_capabilities_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    governance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    trace_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_tenant_status
    ON workflow_executions (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_definition
    ON workflow_executions (workflow_key, workflow_version);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_created_at
    ON workflow_executions (created_at);


CREATE TABLE IF NOT EXISTS workflow_step_executions (
    workflow_step_execution_id TEXT PRIMARY KEY,
    workflow_execution_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    capability_ref_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL,
    attempt_no INTEGER NOT NULL DEFAULT 1,
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NULL,
    error_text TEXT NULL,
    retry_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    timeout_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    compensation_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    trace_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_step_executions_execution_status
    ON workflow_step_executions (workflow_execution_id, status);

CREATE INDEX IF NOT EXISTS idx_workflow_step_executions_node_attempt
    ON workflow_step_executions (workflow_execution_id, node_id, attempt_no);


CREATE TABLE IF NOT EXISTS workflow_execution_events (
    workflow_execution_event_id BIGSERIAL PRIMARY KEY,
    workflow_execution_id TEXT NOT NULL,
    workflow_step_execution_id TEXT NULL,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_execution_events_execution_created_at
    ON workflow_execution_events (workflow_execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_workflow_execution_events_step_created_at
    ON workflow_execution_events (workflow_step_execution_id, created_at);

COMMIT;