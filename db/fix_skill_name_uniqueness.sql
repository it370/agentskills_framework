-- CRITICAL FIX: Allow same skill names in different workspaces
-- This migration fixes a data corruption bug where creating a skill with the same name
-- in a different workspace would overwrite the existing skill.

-- Step 1: Drop the global UNIQUE constraint on name
ALTER TABLE dynamic_skills DROP CONSTRAINT IF EXISTS dynamic_skills_name_key;

-- Step 2: Drop the global UNIQUE constraint on module_name
ALTER TABLE dynamic_skills DROP CONSTRAINT IF EXISTS dynamic_skills_module_name_key;

-- Step 3: Drop any previous non-unique indexes from earlier iterations
DROP INDEX IF EXISTS idx_dynamic_skills_workspace_name;
DROP INDEX IF EXISTS idx_dynamic_skills_workspace_module;

-- Step 4: Enforce uniqueness within a workspace (required for module namespaces)
ALTER TABLE dynamic_skills
    ADD CONSTRAINT dynamic_skills_workspace_name_key UNIQUE (workspace_id, name);

ALTER TABLE dynamic_skills
    ADD CONSTRAINT dynamic_skills_workspace_module_key UNIQUE (workspace_id, module_name);

-- Step 5: Enforce uniqueness for NULL workspace_id rows (Postgres allows multiple NULLs in UNIQUE constraints)
CREATE UNIQUE INDEX IF NOT EXISTS dynamic_skills_null_workspace_name_key
    ON dynamic_skills (name)
    WHERE workspace_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS dynamic_skills_null_workspace_module_key
    ON dynamic_skills (module_name)
    WHERE workspace_id IS NULL;

-- Comments
COMMENT ON CONSTRAINT dynamic_skills_workspace_name_key ON dynamic_skills
    IS 'Skill names must be unique within a workspace';
COMMENT ON CONSTRAINT dynamic_skills_workspace_module_key ON dynamic_skills
    IS 'Module names must be unique within a workspace';
