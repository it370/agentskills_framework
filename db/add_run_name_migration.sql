-- Migration to add run_name column to existing run_metadata table
-- This is safe to run multiple times (idempotent)

-- Add run_name column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'run_metadata' 
        AND column_name = 'run_name'
    ) THEN
        ALTER TABLE run_metadata ADD COLUMN run_name TEXT;
        
        -- Backfill existing rows with thread_id as run_name
        UPDATE run_metadata SET run_name = thread_id WHERE run_name IS NULL;
        
        RAISE NOTICE 'Added run_name column to run_metadata table';
    ELSE
        RAISE NOTICE 'run_name column already exists';
    END IF;
END $$;

-- Add comment
COMMENT ON COLUMN run_metadata.run_name IS 'Human-friendly name for the run (optional, defaults to thread_id if not provided)';
