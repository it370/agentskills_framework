-- Workspace schema
-- Provides per-user isolated project areas with default workspace support

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    -- 8-char workspace code used for namespacing dynamic skill modules
    -- Must be a valid Python identifier segment: starts with a letter, followed by [a-z0-9_]
    code TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT workspaces_user_name_unique UNIQUE (user_id, name)
);

-- Ensure column exists even for existing databases (CREATE TABLE IF NOT EXISTS won't add new columns)
ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS code TEXT;

-- Workspace code generator (collision-resistant; uniqueness enforced by index below).
-- We intentionally force first char to [a-z] so it's safe for Python module paths.
CREATE OR REPLACE FUNCTION generate_workspace_code()
RETURNS TEXT AS $$
DECLARE
    first_char TEXT;
    rest_chars TEXT;
BEGIN
    first_char := chr(97 + floor(random() * 26)::int); -- a-z
    rest_chars := substring(replace(uuid_generate_v4()::text, '-', ''), 1, 7); -- hex
    RETURN first_char || rest_chars;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- Backfill + enforce code for existing/new workspaces
UPDATE workspaces
SET code = generate_workspace_code()
WHERE code IS NULL OR btrim(code) = '';

ALTER TABLE workspaces
    ALTER COLUMN code SET DEFAULT generate_workspace_code(),
    ALTER COLUMN code SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_code_unique ON workspaces(code);

-- Ensure a single default per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_default_per_user
    ON workspaces(user_id)
    WHERE is_default = TRUE;

-- Basic lookup indexes
CREATE INDEX IF NOT EXISTS idx_workspaces_user_id ON workspaces(user_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_name ON workspaces(name);

-- Maintain updated_at timestamp
CREATE OR REPLACE FUNCTION update_workspaces_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_workspaces_timestamp
    BEFORE UPDATE ON workspaces
    FOR EACH ROW
    EXECUTE FUNCTION update_workspaces_timestamp();

COMMENT ON TABLE workspaces IS 'Per-user project areas that isolate skills and runs';
COMMENT ON COLUMN workspaces.name IS 'Workspace name unique per user';
COMMENT ON COLUMN workspaces.code IS '8-char unique code used for dynamic module namespacing';
COMMENT ON COLUMN workspaces.is_default IS 'Whether this workspace is the user''s default';
