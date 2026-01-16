-- Migration to add workspace isolation to skills and runs

-- Add workspace awareness to dynamic skills
ALTER TABLE dynamic_skills
    ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_dynamic_skills_workspace ON dynamic_skills(workspace_id);
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_owner ON dynamic_skills(owner_id);
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_public ON dynamic_skills(is_public);

-- Add workspace awareness to run metadata
ALTER TABLE run_metadata
    ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_run_metadata_workspace ON run_metadata(workspace_id);

-- Backfill defaults: create a 'default' workspace for every user if missing
DO $$
DECLARE
    u RECORD;
BEGIN
    FOR u IN SELECT id FROM users LOOP
        INSERT INTO workspaces (user_id, name, is_default)
        VALUES (u.id, 'default', TRUE)
        ON CONFLICT (user_id, name) DO NOTHING;
    END LOOP;
END $$;

-- Align dynamic skill ownership based on created_by username when possible
UPDATE dynamic_skills ds
SET owner_id = u.id
FROM users u
WHERE ds.owner_id IS NULL
  AND ds.created_by = u.username;

-- Attach skills to the owner's default workspace
UPDATE dynamic_skills ds
SET workspace_id = ws.id
FROM workspaces ws
WHERE ds.workspace_id IS NULL
  AND ds.owner_id = ws.user_id
  AND ws.is_default = TRUE;

-- Fallback: attach orphaned skills to the system user's default workspace when available
UPDATE dynamic_skills ds
SET workspace_id = ws.id,
    owner_id = COALESCE(ds.owner_id, ws.user_id)
FROM workspaces ws
JOIN users u ON ws.user_id = u.id
WHERE ds.workspace_id IS NULL
  AND u.username = 'system'
  AND ws.is_default = TRUE;

-- Backfill runs to default workspace of the owner when available
UPDATE run_metadata rm
SET workspace_id = ws.id
FROM workspaces ws
WHERE rm.workspace_id IS NULL
  AND rm.user_id = ws.user_id
  AND ws.is_default = TRUE;

-- Fallback: attach orphaned runs to system default workspace when available
UPDATE run_metadata rm
SET workspace_id = ws.id
FROM workspaces ws
JOIN users u ON ws.user_id = u.id
WHERE rm.workspace_id IS NULL
  AND u.username = 'system'
  AND ws.is_default = TRUE;

COMMENT ON COLUMN dynamic_skills.workspace_id IS 'Workspace that owns this skill';
COMMENT ON COLUMN dynamic_skills.owner_id IS 'User who owns this skill';
COMMENT ON COLUMN dynamic_skills.is_public IS 'Whether the skill is visible outside its workspace';
COMMENT ON COLUMN run_metadata.workspace_id IS 'Workspace associated with this run';
