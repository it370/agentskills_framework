-- Migration to add user tracking to existing tables
-- This adds user_id columns to run_metadata and logs tables

-- Add user_id to run_metadata
ALTER TABLE run_metadata 
ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;

-- Index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_run_metadata_user_id ON run_metadata(user_id);

-- Add user_id to logs (if table exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'logs') THEN
        ALTER TABLE logs 
        ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
        
        CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id);
    END IF;
END $$;

COMMENT ON COLUMN run_metadata.user_id IS 'User who started this workflow run';
