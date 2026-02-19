-- Schema for persisting workflow_ui_update events

CREATE TABLE IF NOT EXISTS thread_workflow_ui_events (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    parent_event_id TEXT,
    phase TEXT,
    node_kind TEXT,
    event_type TEXT NOT NULL DEFAULT 'workflow_ui_update',
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ensure duplicate event_id per thread is not persisted twice
CREATE UNIQUE INDEX IF NOT EXISTS ux_workflow_ui_events_thread_event
ON thread_workflow_ui_events(thread_id, event_id);

CREATE INDEX IF NOT EXISTS idx_workflow_ui_events_thread_id
ON thread_workflow_ui_events(thread_id);

CREATE INDEX IF NOT EXISTS idx_workflow_ui_events_created_at
ON thread_workflow_ui_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_ui_events_thread_time
ON thread_workflow_ui_events(thread_id, created_at DESC);
