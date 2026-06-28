-- migrate_tasks_v2.sql
-- Adds capacity_agent and network_agent columns to the tasks table.
-- Safe to run on existing DB — uses IF NOT EXISTS guards.
-- Run AFTER migrate_tasks.sql (or alongside if starting fresh).
--
-- Usage (PowerShell):
--   Get-Content migrate_tasks_v2.sql | docker exec -i csa_postgres psql -U csa_user -d csa_db

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS capacity_agent VARCHAR,
    ADD COLUMN IF NOT EXISTS network_agent  VARCHAR;

-- Confirm all columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'tasks'
ORDER BY ordinal_position;