# Run List View

This document describes the `run_list_view` PostgreSQL view that provides enriched workflow run data with pre-computed status for the admin UI.

## Purpose

The view solves the problem where the runs list always shows "pending" status by:
1. Pre-computing the status from checkpoint data
2. Extracting commonly needed fields
3. Providing better performance by avoiding client-side computation

## View Definition

```sql
CREATE OR REPLACE VIEW run_list_view AS
SELECT 
    thread_id,
    checkpoint_id,
    checkpoint_ns,
    active_skill,
    history_count,
    status,           -- Pre-computed status
    sop_preview,      -- First 200 chars of SOP
    updated_at,
    checkpoint,       -- Full checkpoint for details
    metadata
FROM checkpoints
WHERE checkpoint_ns = ''  -- Only root checkpoints
ORDER BY updated_at DESC NULLS LAST;
```

## Status Computation Logic

The view computes status using the following priority:

1. **`completed`** - When:
   - `active_skill = 'END'`
   - OR history contains: "reached end", "execution completed", "planner chose end"
   - OR has history but no active_skill (finished cleanly)

2. **`running`** - When:
   - `active_skill` exists and is not 'END' or NULL

3. **`pending`** - Default for all other cases

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | TEXT | Workflow thread identifier |
| `checkpoint_id` | TEXT | Checkpoint identifier |
| `checkpoint_ns` | TEXT | Checkpoint namespace |
| `active_skill` | TEXT | Currently executing skill (NULL if none) |
| `history_count` | INTEGER | Number of history entries |
| `status` | TEXT | Computed status: 'completed', 'running', or 'pending' |
| `sop_preview` | TEXT | First 200 characters of the SOP |
| `updated_at` | TIMESTAMP | Last update timestamp |
| `checkpoint` | JSONB | Full checkpoint data |
| `metadata` | JSONB | Checkpoint metadata |

## Performance

### Indexes

The view benefits from:
- `idx_checkpoints_updated_at` - Fast ordering by timestamp
- Native checkpoint indexes from LangGraph

### Query Performance

```sql
-- Fast: Uses index
SELECT * FROM run_list_view LIMIT 50;

-- Fast: Uses WHERE filter
SELECT * FROM run_list_view WHERE thread_id = 'thread_123';

-- Fast: Status filtering (computed at query time)
SELECT * FROM run_list_view WHERE status = 'running';
```

## API Integration

The `/admin/runs` endpoint uses this view when PostgreSQL is available:

```python
@api.get("/admin/runs")
async def list_runs(limit: int = 50):
    # Uses run_list_view for pre-computed status
    rows = await query_view(limit)
    return {"runs": rows}
```

### Response Example

```json
{
  "runs": [
    {
      "thread_id": "thread_abc123",
      "checkpoint_id": "1ef...",
      "active_skill": "ProfileRetriever",
      "history_count": 5,
      "status": "running",
      "sop_preview": "Retrieve candidate profile and verify...",
      "updated_at": "2025-01-08T15:30:00Z",
      "checkpoint": {...},
      "metadata": {...}
    }
  ]
}
```

## Frontend Usage

The frontend automatically uses the pre-computed status when available:

```typescript
function normalizeRun(cp: CheckpointTuple | RunSummary): RunRow {
  // If API provided status, use it directly
  if ('status' in cp && cp.status) {
    return {
      thread_id: cp.thread_id,
      status: cp.status,  // ✓ Pre-computed!
      // ...
    };
  }
  
  // Fallback: compute from checkpoint
  // (only needed if view isn't available)
  // ...
}
```

## Setup

### 1. Apply the View

```bash
# Apply just the view
python db/apply_run_list_view.py

# Or apply all schemas
python db/setup_database.py
```

### 2. Verify

```sql
-- Check view exists
SELECT COUNT(*) FROM information_schema.views 
WHERE table_name = 'run_list_view';

-- Test the view
SELECT thread_id, status, active_skill, history_count 
FROM run_list_view 
LIMIT 10;
```

### 3. Check API

```bash
# API should now return status field
curl http://localhost:8000/admin/runs

# Response includes status:
# {
#   "runs": [{
#     "thread_id": "...",
#     "status": "running",  ← Pre-computed!
#     ...
#   }]
# }
```

## Maintenance

### Updating Status Logic

To change status computation logic:

1. Edit `db/run_list_view.sql`
2. Run `python db/apply_run_list_view.py`
3. Test with `SELECT * FROM run_list_view LIMIT 1;`

The view is automatically updated (CREATE OR REPLACE).

### Debugging

Check what status a specific thread would get:

```sql
SELECT 
    thread_id,
    checkpoint->'channel_values'->>'active_skill' as active_skill,
    jsonb_array_length(checkpoint->'channel_values'->'history') as history_count,
    -- Status computation inline
    CASE
        WHEN checkpoint->'channel_values'->>'active_skill' = 'END' THEN 'completed'
        WHEN checkpoint->'channel_values'->>'active_skill' IS NOT NULL THEN 'running'
        ELSE 'pending'
    END as computed_status
FROM checkpoints 
WHERE thread_id = 'thread_abc123';
```

## Migration

If you have existing deployments:

1. **Old behavior**: Frontend computes status from checkpoint
2. **New behavior**: View pre-computes status
3. **Compatibility**: Frontend has fallback for both

The migration is **non-breaking** - old clients continue working.

## Benefits

✅ **Accurate Status** - No more "all pending"  
✅ **Better Performance** - Computed once in DB, not per-client  
✅ **Consistent Logic** - Single source of truth  
✅ **Easy Queries** - Filter by status efficiently  
✅ **Maintainable** - Update logic in one place

