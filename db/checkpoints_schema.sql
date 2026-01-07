-- Schema for LangGraph Postgres checkpointer tables.
-- Sourced from langgraph.checkpoint.postgres MIGRATIONS (v3.0.2 at time of generation).
-- Note: CREATE INDEX CONCURRENTLY cannot run inside a transaction block.

-- 0. Migration tracking
CREATE TABLE IF NOT EXISTS checkpoint_migrations (
    v INTEGER PRIMARY KEY
);

-- 1. Checkpoints table
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- 2. Blobs table
CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- 3. Writes table
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- 4. Allow null blobs (matches migration 4)
ALTER TABLE checkpoint_blobs ALTER COLUMN blob DROP NOT NULL;

-- 5. No-op migration placeholder
SELECT 1;

-- 6-8. Performance indexes (run outside of a transaction)
CREATE INDEX CONCURRENTLY IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);

-- 9. Additional metadata for writes
ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT '';

