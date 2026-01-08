-- Schema for tracking run metadata at start time
-- This table stores the initial configuration and inputs for each run
-- Enables rerun functionality with same inputs

CREATE TABLE IF NOT EXISTS run_metadata (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT UNIQUE NOT NULL,
    run_name TEXT,  -- Human-friendly name (optional, defaults to thread_id)
    sop TEXT NOT NULL,
    initial_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    parent_thread_id TEXT,  -- For reruns, tracks the original thread
    rerun_count INTEGER DEFAULT 0,  -- How many times this has been rerun
    metadata JSONB DEFAULT '{}'::jsonb  -- Additional metadata (user, tags, etc.)
);

-- Index for fast lookups by thread_id
CREATE INDEX IF NOT EXISTS idx_run_metadata_thread_id ON run_metadata(thread_id);

-- Index for finding reruns
CREATE INDEX IF NOT EXISTS idx_run_metadata_parent ON run_metadata(parent_thread_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_run_metadata_created_at ON run_metadata(created_at DESC);

COMMENT ON TABLE run_metadata IS 'Stores initial configuration and inputs for each workflow run to enable reruns with same parameters';
COMMENT ON COLUMN run_metadata.thread_id IS 'Unique identifier for the workflow run (LangGraph thread_id)';
COMMENT ON COLUMN run_metadata.run_name IS 'Human-friendly name for the run (optional, defaults to thread_id if not provided)';
COMMENT ON COLUMN run_metadata.sop IS 'Standard Operating Procedure (layman instructions) for the workflow';
COMMENT ON COLUMN run_metadata.initial_data IS 'Initial data_store JSON passed to the workflow';
COMMENT ON COLUMN run_metadata.parent_thread_id IS 'If this is a rerun, the thread_id of the original run';
COMMENT ON COLUMN run_metadata.rerun_count IS 'Number of times this run has been rerun';
