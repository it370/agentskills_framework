-- Add status tracking columns to run_metadata table
-- This allows the UI to easily query run status without decoding msgpack

ALTER TABLE run_metadata 
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'running',
ADD COLUMN IF NOT EXISTS error_message TEXT,
ADD COLUMN IF NOT EXISTS failed_skill TEXT,
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;

-- Create index for status queries
CREATE INDEX IF NOT EXISTS idx_run_metadata_status ON run_metadata(status);

-- Add comments
COMMENT ON COLUMN run_metadata.status IS 'Current status: running, completed, error';
COMMENT ON COLUMN run_metadata.error_message IS 'Error message if status is error';
COMMENT ON COLUMN run_metadata.failed_skill IS 'Name of skill that failed';
COMMENT ON COLUMN run_metadata.completed_at IS 'Timestamp when workflow completed or failed';
