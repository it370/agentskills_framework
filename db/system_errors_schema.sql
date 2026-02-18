-- Schema for critical system errors that need admin investigation
-- Separate from thread_logs to capture infrastructure/system-level failures

CREATE TABLE IF NOT EXISTS system_errors (
    id BIGSERIAL PRIMARY KEY,
    error_type TEXT NOT NULL,  -- e.g., 'checkpoint_flush_error', 'database_error', 'redis_error'
    severity TEXT NOT NULL,    -- 'warning', 'error', 'critical'
    thread_id TEXT,            -- Associated thread (if applicable)
    error_message TEXT NOT NULL,
    stack_trace TEXT,          -- Full stack trace for debugging
    error_context JSONB,       -- Additional context (e.g., checkpoint count, DB URI, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by TEXT,
    resolution_notes TEXT
);

-- Index for fast lookups by error type
CREATE INDEX IF NOT EXISTS idx_system_errors_type ON system_errors(error_type);

-- Index for unresolved errors (admin dashboard)
CREATE INDEX IF NOT EXISTS idx_system_errors_unresolved ON system_errors(resolved_at) WHERE resolved_at IS NULL;

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_system_errors_created_at ON system_errors(created_at DESC);

-- Index for thread-based lookups
CREATE INDEX IF NOT EXISTS idx_system_errors_thread_id ON system_errors(thread_id) WHERE thread_id IS NOT NULL;

-- Index for severity (to quickly find critical errors)
CREATE INDEX IF NOT EXISTS idx_system_errors_severity ON system_errors(severity, created_at DESC);

-- Composite index for filtering by type and unresolved status
CREATE INDEX IF NOT EXISTS idx_system_errors_type_unresolved ON system_errors(error_type, created_at DESC) WHERE resolved_at IS NULL;

COMMENT ON TABLE system_errors IS 'Critical system errors requiring admin attention, separate from regular thread logs';
COMMENT ON COLUMN system_errors.error_type IS 'Category of error for filtering and alerting';
COMMENT ON COLUMN system_errors.severity IS 'warning: non-critical but notable, error: needs attention, critical: immediate action required';
COMMENT ON COLUMN system_errors.error_context IS 'JSON object with additional debugging context (counts, URIs, config values, etc.)';
COMMENT ON COLUMN system_errors.resolved_at IS 'When an admin marked this error as resolved';
