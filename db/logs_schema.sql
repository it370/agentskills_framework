-- Schema for persisting live logs
-- Each log entry is associated with a thread_id for filtering

CREATE TABLE IF NOT EXISTS thread_logs (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    level TEXT DEFAULT 'INFO'
);

-- Index for fast lookups by thread_id
CREATE INDEX IF NOT EXISTS idx_thread_logs_thread_id ON thread_logs(thread_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_thread_logs_created_at ON thread_logs(created_at DESC);

-- Composite index for thread + time
CREATE INDEX IF NOT EXISTS idx_thread_logs_thread_time ON thread_logs(thread_id, created_at DESC);

