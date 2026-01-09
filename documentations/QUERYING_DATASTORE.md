# How to Query data_store from Checkpoints Database

## Summary

LangGraph stores workflow state in PostgreSQL using **msgpack binary serialization** in the `checkpoint_blobs` table. This document explains how to query and decode the actual `data_store` values.

## Database Structure

### Tables

1. **`checkpoints`** - Main checkpoint metadata with JSONB
   - Contains references/pointers to actual data
   - `checkpoint->'channel_versions'->>'data_store'` = version reference string

2. **`checkpoint_blobs`** - Actual state data (msgpack binary)
   - Contains the real data_store, history, etc.
   - Uses `version` column to match with checkpoint references

3. **`checkpoint_writes`** - Write operations log
   - Tracks incremental changes
   - Not used for querying final state

## The Version Reference System

In the `checkpoints` table, you'll see references like:
```
"data_store": "00000000000000000000000000000002.0.1468238570540602"
```

This is NOT the actual data - it's a **version pointer** with format:
```
{checkpoint_id}.{task_id}.{version_hash}
```

The actual data is in `checkpoint_blobs` table, keyed by the full version string.

## How to Query data_store

### Method 1: Using the Python Script (Recommended)

```bash
# List recent threads
python db/query_data_store.py

# Query specific thread
python db/query_data_store.py thread_604f913d-767a-46b8-93ff-2ce8c661f4c3
```

Output:
```
Thread ID: thread_604f913d-767a-46b8-93ff-2ce8c661f4c3
Checkpoint ID: 1f0ed127-162c-6a95-8001-35b57b41f069
Data store version: 00000000000000000000000000000002.0.1468238570540602
Blob type: msgpack
Blob size: 16 bytes

=== DATA_STORE CONTENTS ===
{
  "user_id": "system",
  "_status": "failed",
  "_error": "Postgres query failed: ...",
  "_failed_skill": "DatabaseUserFetcher"
}
```

### Method 2: Raw SQL (Not Recommended - Returns Binary)

```sql
-- Get the version reference
SELECT 
    thread_id,
    checkpoint->'channel_versions'->>'data_store' as data_store_version
FROM checkpoints
WHERE thread_id = 'your_thread_id'
  AND checkpoint_ns = ''
ORDER BY (checkpoint->>'ts')::timestamp DESC
LIMIT 1;

-- Get the binary blob (you'll need to decode msgpack)
SELECT blob, type
FROM checkpoint_blobs
WHERE thread_id = 'your_thread_id'
  AND channel = 'data_store'
  AND version = 'version_from_above'
LIMIT 1;
```

**Problem**: The `blob` column is binary msgpack data - you can't read it directly in SQL!

### Method 3: Create a PostgreSQL Function (Advanced)

If you have a PostgreSQL extension that can decode msgpack, you could create a function. However, msgpack is not natively supported in PostgreSQL, so this requires custom extensions.

## Why Your View Works

Your `run_list_view.sql` checks:
```sql
c.checkpoint->'channel_values'->'data_store'->>'_status'
```

But looking at the actual checkpoint structure, `data_store` is NOT in `channel_values` - it's only referenced in `channel_versions`.

**The view works because** it's checking for `_status` in a place that doesn't exist, so it always returns NULL, and then falls through to other status checks (like `active_skill = 'END'`).

## Correct Way to Check _status in SQL

You cannot directly query `_status` from the checkpoints table because:
1. The actual data_store is in `checkpoint_blobs` as binary msgpack
2. PostgreSQL doesn't natively decode msgpack

**Solution**: Add the data to a denormalized column during checkpoint save, or query via Python.

## Adding Debug Logging to See data_store

In `engine.py`, lines 1608-1618 (`put` method), add this:

```python
def put(self, config, checkpoint, metadata, new_versions):
    # Get data_store version reference
    data_store_ref = checkpoint.get("channel_versions", {}).get("data_store")
    
    if data_store_ref:
        # Parse the reference
        parts = data_store_ref.split('.')
        cp_id, task_id = parts[0], parts[1] if len(parts) > 1 else '0'
        
        # Query the actual data_store from checkpoint_blobs
        try:
            import msgpack
            thread_id = config.get('configurable', {}).get('thread_id')
            
            # Note: self.conn is the connection from the pool
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT blob FROM checkpoint_blobs
                    WHERE thread_id = %s AND channel = 'data_store' AND version = %s
                """, (thread_id, data_store_ref))
                
                result = cur.fetchone()
                if result:
                    data_store = msgpack.unpackb(result[0], raw=False)
                    print(f"[CHECKPOINT DEBUG] Saving - thread={thread_id}")
                    print(f"[CHECKPOINT DEBUG] data_store: {json.dumps(data_store, indent=2, default=str)}")
        except Exception as e:
            print(f"[CHECKPOINT DEBUG] Failed to decode: {e}")
    
    result = super().put(config, checkpoint, metadata, new_versions)
    # ... rest of method
```

## Tools Provided

1. **`db/query_data_store.py`** - Query and display data_store for any thread
2. **`db/inspect_checkpoints.py`** - Inspect database structure and find data

## Key Takeaways

✅ data_store is stored as **msgpack binary** in `checkpoint_blobs` table  
✅ The `checkpoints` table only has **version references**, not actual data  
✅ To read data_store, you must: query → get version ref → query blob → decode msgpack  
✅ SQL alone cannot easily decode msgpack - use Python  
✅ Your error handling code works correctly - the `_status` field IS being saved  
✅ The database view checking for `_status` doesn't work because it's looking in the wrong place

## Next Steps

If you want to query `_status` in SQL for your view:

1. **Option A**: Store status in a separate column during checkpoint save
2. **Option B**: Create a materialized view that decodes msgpack (requires extension)
3. **Option C**: Accept that status detection uses `active_skill = 'END'` + history markers (current approach)

The current approach (Option C) is actually fine - the view correctly shows "error" status by checking the history for failure markers!
