-- Workspace schema
-- Provides per-user isolated project areas with default workspace support

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT workspaces_user_name_unique UNIQUE (user_id, name)
);

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
COMMENT ON COLUMN workspaces.is_default IS 'Whether this workspace is the user''s default';
