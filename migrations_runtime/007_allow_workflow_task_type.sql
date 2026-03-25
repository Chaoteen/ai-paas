BEGIN;

DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel
          ON rel.oid = con.conrelid
        JOIN pg_namespace nsp
          ON nsp.oid = rel.relnamespace
        WHERE rel.relname = 'runtime_tasks'
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) ILIKE '%task_type%'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I DROP CONSTRAINT %I',
            'public',
            'runtime_tasks',
            rec.conname
        );
    END LOOP;
END $$;

ALTER TABLE runtime_tasks
    ADD CONSTRAINT ck_runtime_tasks_task_type
    CHECK (task_type IN ('agent', 'generation', 'workflow'));

COMMIT;