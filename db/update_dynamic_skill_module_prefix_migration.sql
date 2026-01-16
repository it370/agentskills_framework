-- Migration: namespace dynamic_skills.module_name with workspace code
-- New convention: module_name = "{workspace_code}.{generate_module_name(name)}"
-- Also updates action_config.module to "dynamic_skills.{module_name}" for python_function skills.
-- Safe to run multiple times.

-- Ensure dependencies exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 0) Hard stop if there are duplicate skill names within a workspace
DO $$
DECLARE
    dup_count INT;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT workspace_id, name
        FROM dynamic_skills
        WHERE workspace_id IS NOT NULL
        GROUP BY workspace_id, name
        HAVING COUNT(*) > 1
    ) d;

    IF dup_count > 0 THEN
        RAISE EXCEPTION 'Cannot apply module prefix migration: duplicate (workspace_id, name) rows exist in dynamic_skills. Resolve duplicates first.';
    END IF;
END $$;

-- 1) Ensure trigger recomputes module_name when workspace_id changes
DROP TRIGGER IF EXISTS trigger_auto_generate_module_name ON dynamic_skills;

CREATE TRIGGER trigger_auto_generate_module_name
    BEFORE INSERT OR UPDATE OF name, workspace_id ON dynamic_skills
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_module_name();

-- 2) Backfill / normalize module_name to "code.base"
UPDATE dynamic_skills ds
SET module_name = ws.code || '.' || generate_module_name(ds.name)
FROM workspaces ws
WHERE ds.workspace_id = ws.id
  AND (
      ds.module_name IS NULL
      OR ds.module_name != ws.code || '.' || generate_module_name(ds.name)
  );

-- 3) Update action_config.module for python_function skills (DB skills)
UPDATE dynamic_skills ds
SET action_config = jsonb_set(
    ds.action_config,
    '{module}',
    to_jsonb('dynamic_skills.' || ds.module_name),
    true
)
WHERE ds.action_config IS NOT NULL
  AND (ds.action_config->>'type') = 'python_function'
  AND (ds.action_config ? 'module')
  AND (
      ds.action_config->>'module' IS NULL
      OR ds.action_config->>'module' != 'dynamic_skills.' || ds.module_name
  );

