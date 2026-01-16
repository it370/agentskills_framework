-- Migration: add workspace.code (8-char unique) used for module namespacing
-- Safe to run multiple times.

-- Ensure UUID extension exists (used for code generation seed)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1) Add column (nullable at first for backfill)
ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS code TEXT;

-- 2) Generator (first char forced to [a-z] to be a valid Python module segment)
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

-- 3) Backfill missing codes
UPDATE workspaces
SET code = generate_workspace_code()
WHERE code IS NULL OR btrim(code) = '';

-- 4) Enforce default + NOT NULL
ALTER TABLE workspaces
    ALTER COLUMN code SET DEFAULT generate_workspace_code();

-- NOT NULL may fail if rows exist with NULL after backfill; keep it strict
ALTER TABLE workspaces
    ALTER COLUMN code SET NOT NULL;

-- 5) Uniqueness enforcement
CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_code_unique ON workspaces(code);

COMMENT ON COLUMN workspaces.code IS '8-char unique code used for dynamic module namespacing';
