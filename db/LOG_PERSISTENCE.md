# Log Persistence System

This directory contains the database schema and migration scripts for persisting thread logs to PostgreSQL.

## Overview

The log persistence system stores all logs emitted during workflow execution, allowing:
- Historical log retrieval for completed runs
- Debugging and auditing capabilities
- Thread-specific log filtering

## Database Schema

The `thread_logs` table stores log entries with the following structure:

```sql
CREATE TABLE thread_logs (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT,                      -- Associated workflow thread
    message TEXT NOT NULL,               -- Log message content
    created_at TIMESTAMP WITH TIME ZONE, -- When the log was created
    level TEXT DEFAULT 'INFO'            -- Log level (INFO, WARN, ERROR, DEBUG)
);
```

### Indexes

- `idx_thread_logs_thread_id`: Fast lookups by thread_id
- `idx_thread_logs_created_at`: Time-based queries
- `idx_thread_logs_thread_time`: Combined thread + time queries

## Setup

### 1. Apply the Schema

Run the migration script to create the table:

```bash
python db/apply_logs_schema.py
```

This will:
- Read `DATABASE_URL` from your environment
- Create the `thread_logs` table
- Set up all indexes
- Verify the table was created

### 2. Verify Setup

The system will automatically:
- Initialize a sync connection pool on startup (Windows compatible)
- Access the pool via `asyncio.to_thread()` to avoid blocking
- Begin persisting logs to the database
- Send logs to WebSocket clients

Check the console for initialization messages:
```
[LOG_PERSIST] Log persistence initialized with sync pool.
```

**Note:** The system uses sync database operations wrapped with `asyncio.to_thread()` for Windows compatibility. This avoids the `ProactorEventLoop` issues with async psycopg operations.

## Usage

### Backend

Logs are automatically persisted when using the standard logging functions:

```python
from log_stream import publish_log, emit_log, set_log_context

# Set thread context (done automatically in workflows)
set_log_context("thread_abc123")

# Logs will include thread_id automatically
await publish_log("Processing started")
emit_log("Synchronous log message")

# Or explicitly pass thread_id
await publish_log("Custom message", thread_id="thread_xyz", level="WARN")
```

### API

Retrieve historical logs for a thread:

```http
GET /admin/runs/{thread_id}/logs?limit=1000
```

Response:
```json
{
  "logs": [
    {
      "id": 1,
      "thread_id": "thread_abc123",
      "message": "[API] Start requested for thread=thread_abc123",
      "created_at": "2025-01-08T10:30:00Z",
      "level": "INFO"
    }
  ],
  "count": 1
}
```

### Frontend

The admin UI automatically:
1. Loads historical logs when viewing a thread detail page
2. Merges them with live WebSocket logs
3. Filters by thread_id for accurate display

## Architecture

```
┌─────────────┐
│  Workflow   │
│  Execution  │
└──────┬──────┘
       │ publish_log()
       ▼
┌──────────────────┐
│   log_stream.py  │
│  ┌─────────────┐ │
│  │  Broadcast  │ │──────► WebSocket Clients (Live)
│  │  to WS      │ │
│  └─────────────┘ │
│  ┌─────────────┐ │
│  │  Persist to │ │──────► PostgreSQL (History)
│  │  Database   │ │
│  └─────────────┘ │
└──────────────────┘
```

## Performance Considerations

- Database operations use sync pool with `asyncio.to_thread()` for non-blocking execution
- Windows compatible (avoids ProactorEventLoop issues with async psycopg)
- Failed DB writes don't stop log broadcasting
- Connection pool limits: min=1, max=10
- Default query limit: 1000 logs per thread
- Operations are executed in separate threads to avoid blocking the event loop

## Troubleshooting

### Logs not persisting

Check the console for errors:
```
[LOG_PERSIST] Failed to persist log: <error>
```

Verify:
1. `DATABASE_URL` is set correctly
2. Table exists: `SELECT * FROM thread_logs LIMIT 1;`
3. Database user has INSERT permissions

### Historical logs not loading

Check browser console for API errors:
```javascript
Failed to fetch logs for thread: <thread_id>
```

Verify:
1. Backend is running
2. `/admin/runs/{thread_id}/logs` endpoint is accessible
3. Thread exists in the database

## Maintenance

### Clean up old logs

To prevent unlimited growth, periodically clean old logs:

```sql
-- Delete logs older than 30 days
DELETE FROM thread_logs 
WHERE created_at < NOW() - INTERVAL '30 days';

-- Or keep only the latest 10,000 logs per thread
DELETE FROM thread_logs 
WHERE id NOT IN (
    SELECT id FROM thread_logs 
    ORDER BY created_at DESC 
    LIMIT 10000
);
```

Consider setting up a scheduled job (cron) for automatic cleanup.

