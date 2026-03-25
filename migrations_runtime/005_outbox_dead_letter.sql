BEGIN;

ALTER TABLE runtime_outbox_events
DROP CONSTRAINT IF EXISTS chk_runtime_outbox_status;

ALTER TABLE runtime_outbox_events
ADD CONSTRAINT chk_runtime_outbox_status
CHECK (
    status IN (
        'pending',
        'publishing',
        'published',
        'failed',
        'dead_letter'
    )
);

COMMIT;
