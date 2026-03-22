BEGIN;

-- ============================================================================
-- Phase 17 P0
-- Formalize dead_letter as a real runtime_outbox_events database state.
--
-- Why this migration exists:
-- - The Python repository/relay code already supports dead_letter.
-- - The existing DB constraint in 004_tasks_outbox.sql does NOT.
-- - This migration upgrades the real Postgres schema to match runtime behavior.
-- ============================================================================

-- 1) Expand the runtime_outbox_events.status check constraint so dead_letter
--    becomes a first-class persisted state.
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

-- 2) Optional operational index for DLQ inspection / replay tooling.
--    Kept partial so it stays small and production-friendly.
CREATE INDEX IF NOT EXISTS idx_runtime_outbox_dead_letter_created_at
    ON runtime_outbox_events (created_at DESC, event_id DESC)
    WHERE status = 'dead_letter';

COMMIT;