BEGIN;

CREATE TABLE IF NOT EXISTS workflow_products (
    product_key TEXT NOT NULL,
    product_version TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    public_api_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ui_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    bound_workflow_key TEXT NOT NULL,
    bound_workflow_version TEXT NOT NULL,
    default_input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_mapping_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    governance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    visibility TEXT NOT NULL DEFAULT 'tenant',
    created_by TEXT NULL,
    updated_by TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (product_key, product_version)
);

CREATE INDEX IF NOT EXISTS idx_workflow_products_status
    ON workflow_products(status);

CREATE INDEX IF NOT EXISTS idx_workflow_products_workflow_binding
    ON workflow_products(bound_workflow_key, bound_workflow_version);

COMMIT;