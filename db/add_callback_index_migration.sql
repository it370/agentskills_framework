-- Migration: Add GIN index on metadata JSONB column for faster callback_url lookups
-- This optimizes the callback feature when checking for callback_url existence

-- Create GIN index on metadata column for JSONB operations
CREATE INDEX IF NOT EXISTS idx_run_metadata_metadata_gin ON run_metadata USING GIN (metadata);

-- Optional: Create expression index specifically for callback_url (even faster for this specific use case)
CREATE INDEX IF NOT EXISTS idx_run_metadata_callback_url ON run_metadata ((metadata->>'callback_url')) 
WHERE metadata ? 'callback_url';

COMMENT ON INDEX idx_run_metadata_metadata_gin IS 'GIN index for fast JSONB queries on metadata column';
COMMENT ON INDEX idx_run_metadata_callback_url IS 'Partial index for runs with callback_url configured (optimizes callback invocation)';
