BEGIN;

CREATE TABLE IF NOT EXISTS recording_sessions (
    recording_session_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    status TEXT NOT NULL,
    distillation_mode TEXT NOT NULL DEFAULT 'dialogue_only',
    current_phase TEXT NOT NULL DEFAULT 'capture',
    title TEXT NOT NULL,
    description TEXT NULL,
    context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    latest_skill_draft_id TEXT NULL,
    created_by TEXT NULL,
    updated_by TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_recording_sessions_source_type
        CHECK (source_type IN ('dialogue', 'ui_recording')),
    CONSTRAINT chk_recording_sessions_status
        CHECK (status IN ('draft', 'collecting', 'distilled', 'archived')),
    CONSTRAINT chk_recording_sessions_distillation_mode
        CHECK (distillation_mode IN ('record_only', 'dialogue_only', 'hybrid')),
    CONSTRAINT chk_recording_sessions_current_phase
        CHECK (current_phase IN ('capture', 'organize', 'distill', 'review'))
);

CREATE INDEX IF NOT EXISTS idx_recording_sessions_tenant_created_at
    ON recording_sessions(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recording_sessions_tenant_status_created_at
    ON recording_sessions(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recording_sessions_tenant_source_created_at
    ON recording_sessions(tenant_id, source_type, created_at DESC);

CREATE TABLE IF NOT EXISTS recording_action_events (
    recording_action_event_id TEXT PRIMARY KEY,
    recording_session_id TEXT NOT NULL REFERENCES recording_sessions(recording_session_id),
    tenant_id TEXT NOT NULL,
    sequence_no BIGINT NOT NULL,
    idempotency_key TEXT NULL,
    source_event_id TEXT NULL,
    event_timestamp TIMESTAMPTZ NULL,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_ref_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_recording_action_events_event_type
        CHECK (event_type IN ('dialogue_step', 'ui_action', 'system_inference')),
    CONSTRAINT chk_recording_action_events_actor_type
        CHECK (actor_type IN ('user', 'assistant', 'recorder', 'system')),
    CONSTRAINT uq_recording_action_events_session_sequence
        UNIQUE (recording_session_id, sequence_no)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recording_action_events_session_idempotency
    ON recording_action_events(recording_session_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recording_action_events_session_sequence
    ON recording_action_events(recording_session_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_recording_action_events_tenant_session_created_at
    ON recording_action_events(tenant_id, recording_session_id, created_at);

CREATE TABLE IF NOT EXISTS skill_drafts (
    skill_draft_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    recording_session_id TEXT NULL REFERENCES recording_sessions(recording_session_id),
    previous_skill_draft_id TEXT NULL REFERENCES skill_drafts(skill_draft_id),
    promoted_skill_id TEXT NULL,
    promoted_skill_version_id TEXT NULL,
    draft_key TEXT NOT NULL,
    draft_version TEXT NOT NULL,
    status TEXT NOT NULL,
    name TEXT NOT NULL,
    intent_summary TEXT NULL,
    distillation_source_type TEXT NOT NULL,
    input_schema_json JSONB NOT NULL DEFAULT '{"type":"object","properties":{},"required":[]}'::jsonb,
    output_schema_json JSONB NOT NULL DEFAULT '{"type":"object","properties":{},"required":[]}'::jsonb,
    draft_definition_json JSONB NOT NULL DEFAULT '{"draft_type":"task_skill","steps":[],"inputs":[],"outputs":[],"guardrails":{},"hints":{}}'::jsonb,
    distillation_notes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_binding_json JSONB NOT NULL DEFAULT '{"binding_type":"unbound","target_ref":{"object_type":null,"object_id":null},"config_json":{}}'::jsonb,
    derived_from_json JSONB NOT NULL DEFAULT '{"recording_session_id":null,"source_event_range":{"from_sequence_no":null,"to_sequence_no":null},"source_kind":"imported"}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NULL,
    updated_by TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_skill_drafts_status
        CHECK (status IN ('draft', 'reviewing', 'accepted', 'rejected', 'archived')),
    CONSTRAINT chk_skill_drafts_distillation_source_type
        CHECK (distillation_source_type IN ('dialogue', 'ui_recording', 'hybrid', 'imported')),
    CONSTRAINT uq_skill_drafts_tenant_key_version
        UNIQUE (tenant_id, draft_key, draft_version)
);

CREATE INDEX IF NOT EXISTS idx_skill_drafts_tenant_created_at
    ON skill_drafts(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_skill_drafts_tenant_status_created_at
    ON skill_drafts(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_skill_drafts_tenant_session_created_at
    ON skill_drafts(tenant_id, recording_session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_skill_drafts_tenant_key_created_at
    ON skill_drafts(tenant_id, draft_key, created_at DESC);

COMMIT;