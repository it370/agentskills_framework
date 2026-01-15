-- Migration: Convert primary keys to UUID and add module_name to dynamic_skills
-- This migration:
-- 1. Changes users.id from BIGSERIAL to UUID
-- 2. Changes dynamic_skills.id from BIGSERIAL to UUID
-- 3. Adds module_name column to dynamic_skills with auto-generation from name
-- 4. Updates all foreign key references to use UUID

-- NOTE: This migration requires the uuid-ossp extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

BEGIN;

-- =====================================================
-- STEP 1: Backup existing data (optional but recommended)
-- =====================================================
-- For safety, we'll use a transaction. Consider creating table backups first:
-- CREATE TABLE users_backup AS SELECT * FROM users;
-- CREATE TABLE dynamic_skills_backup AS SELECT * FROM dynamic_skills;

-- =====================================================
-- STEP 2: Add module_name column to dynamic_skills
-- =====================================================

-- Add module_name column with generated default
ALTER TABLE dynamic_skills
ADD COLUMN IF NOT EXISTS module_name TEXT;

-- Create function to convert name to valid Python module name
CREATE OR REPLACE FUNCTION generate_module_name(skill_name TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Convert to lowercase
    -- Replace spaces and special characters with underscores
    -- Remove consecutive underscores
    -- Trim leading/trailing underscores
    RETURN TRIM(BOTH '_' FROM 
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                LOWER(skill_name), 
                '[^a-z0-9_]', 
                '_', 
                'g'
            ),
            '_+',
            '_',
            'g'
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Populate module_name for existing rows
UPDATE dynamic_skills
SET module_name = generate_module_name(name)
WHERE module_name IS NULL;

-- Make module_name NOT NULL and add UNIQUE constraint
ALTER TABLE dynamic_skills
ALTER COLUMN module_name SET NOT NULL,
ADD CONSTRAINT unique_module_name UNIQUE (module_name);

-- Create trigger to auto-populate module_name on INSERT/UPDATE
CREATE OR REPLACE FUNCTION auto_generate_module_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.module_name = generate_module_name(NEW.name);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_auto_generate_module_name ON dynamic_skills;
CREATE TRIGGER trigger_auto_generate_module_name
    BEFORE INSERT OR UPDATE OF name ON dynamic_skills
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_module_name();

-- Add index for module_name
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_module_name ON dynamic_skills(module_name);

-- Add comment
COMMENT ON COLUMN dynamic_skills.module_name IS 'Auto-generated Python module name from skill name (lowercase, valid identifier)';

-- =====================================================
-- STEP 3: Convert users table to UUID
-- =====================================================

-- Add new UUID column
ALTER TABLE users ADD COLUMN id_uuid UUID DEFAULT uuid_generate_v4();

-- Populate UUID for existing rows (already done with DEFAULT)
-- Make sure all rows have UUIDs
UPDATE users SET id_uuid = uuid_generate_v4() WHERE id_uuid IS NULL;

-- Update foreign key references in password_reset_tokens
ALTER TABLE password_reset_tokens ADD COLUMN user_id_uuid UUID;
UPDATE password_reset_tokens prt
SET user_id_uuid = u.id_uuid
FROM users u
WHERE prt.user_id = u.id;

-- Update foreign key references in user_sessions
ALTER TABLE user_sessions ADD COLUMN user_id_uuid UUID;
UPDATE user_sessions us
SET user_id_uuid = u.id_uuid
FROM users u
WHERE us.user_id = u.id;

-- Update foreign key references in run_metadata (if exists)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'run_metadata' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE run_metadata ADD COLUMN user_id_uuid UUID;
        UPDATE run_metadata rm
        SET user_id_uuid = u.id_uuid
        FROM users u
        WHERE rm.user_id = u.id;
    END IF;
END $$;

-- Update foreign key references in logs (if exists)
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'logs' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE logs ADD COLUMN user_id_uuid UUID;
        UPDATE logs l
        SET user_id_uuid = u.id_uuid
        FROM users u
        WHERE l.user_id = u.id;
    END IF;
END $$;

-- Drop old foreign key constraints
ALTER TABLE password_reset_tokens DROP CONSTRAINT IF EXISTS password_reset_tokens_user_id_fkey;
ALTER TABLE user_sessions DROP CONSTRAINT IF EXISTS user_sessions_user_id_fkey;

DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE table_name = 'run_metadata' 
        AND constraint_name LIKE '%user_id%'
        AND constraint_type = 'FOREIGN KEY'
    ) THEN
        ALTER TABLE run_metadata DROP CONSTRAINT IF EXISTS run_metadata_user_id_fkey;
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE table_name = 'logs' 
        AND constraint_name LIKE '%user_id%'
        AND constraint_type = 'FOREIGN KEY'
    ) THEN
        ALTER TABLE logs DROP CONSTRAINT IF EXISTS logs_user_id_fkey;
    END IF;
END $$;

-- Drop old indexes
DROP INDEX IF EXISTS idx_run_metadata_user_id;
DROP INDEX IF EXISTS idx_logs_user_id;

-- Drop old primary key and rename UUID column
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey CASCADE;
ALTER TABLE users DROP COLUMN id;
ALTER TABLE users RENAME COLUMN id_uuid TO id;
ALTER TABLE users ADD PRIMARY KEY (id);

-- Drop old foreign key columns and rename UUID columns
ALTER TABLE password_reset_tokens DROP COLUMN user_id;
ALTER TABLE password_reset_tokens RENAME COLUMN user_id_uuid TO user_id;
ALTER TABLE password_reset_tokens ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE password_reset_tokens 
    ADD CONSTRAINT password_reset_tokens_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE user_sessions DROP COLUMN user_id;
ALTER TABLE user_sessions RENAME COLUMN user_id_uuid TO user_id;
ALTER TABLE user_sessions ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE user_sessions 
    ADD CONSTRAINT user_sessions_user_id_fkey 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Update run_metadata if exists
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'run_metadata' AND column_name = 'user_id_uuid'
    ) THEN
        ALTER TABLE run_metadata DROP COLUMN user_id;
        ALTER TABLE run_metadata RENAME COLUMN user_id_uuid TO user_id;
        ALTER TABLE run_metadata 
            ADD CONSTRAINT run_metadata_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        CREATE INDEX idx_run_metadata_user_id ON run_metadata(user_id);
    END IF;
END $$;

-- Update logs if exists
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'logs' AND column_name = 'user_id_uuid'
    ) THEN
        ALTER TABLE logs DROP COLUMN user_id;
        ALTER TABLE logs RENAME COLUMN user_id_uuid TO user_id;
        ALTER TABLE logs 
            ADD CONSTRAINT logs_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        CREATE INDEX idx_logs_user_id ON logs(user_id);
    END IF;
END $$;

-- =====================================================
-- STEP 4: Convert dynamic_skills table to UUID
-- =====================================================

-- Add new UUID column
ALTER TABLE dynamic_skills ADD COLUMN id_uuid UUID DEFAULT uuid_generate_v4();

-- Populate UUID for existing rows
UPDATE dynamic_skills SET id_uuid = uuid_generate_v4() WHERE id_uuid IS NULL;

-- Drop old primary key
ALTER TABLE dynamic_skills DROP CONSTRAINT IF EXISTS dynamic_skills_pkey CASCADE;
ALTER TABLE dynamic_skills DROP COLUMN id;
ALTER TABLE dynamic_skills RENAME COLUMN id_uuid TO id;
ALTER TABLE dynamic_skills ADD PRIMARY KEY (id);

-- =====================================================
-- STEP 5: Update schema files for future installations
-- =====================================================
-- Note: The schema files (users_schema.sql, dynamic_skills_schema.sql) should be 
-- updated manually to use UUID instead of BIGSERIAL for new installations

COMMIT;

-- =====================================================
-- Verification queries
-- =====================================================
-- Run these after migration to verify:
-- SELECT id, username, email FROM users LIMIT 5;
-- SELECT id, name, module_name FROM dynamic_skills LIMIT 5;
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'id';
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dynamic_skills' AND column_name IN ('id', 'module_name');
