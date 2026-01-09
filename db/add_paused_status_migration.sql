-- Migration: Add 'paused' status support to run_metadata
-- This status is used when workflow is paused at HITL or callback nodes

-- Update the comment on the status column to document all valid values
COMMENT ON COLUMN run_metadata.status IS 'Current status: running, completed, error, paused';
