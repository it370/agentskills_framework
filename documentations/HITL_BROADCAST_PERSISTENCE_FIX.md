# HITL Broadcast Persistence Fix

## Problem
When resuming a workflow from HITL (Human-In-The-Loop) pause, the broadcast setting was being retrieved from the workflow's in-memory state at the API endpoint level. This caused issues when:
- The server was restarted between pause and resume
- The checkpoint state was cleared from memory
- The API needed to know whether to enable broadcasting before the workflow nodes started executing

The broadcast context variable would not be properly restored in the background task that resumes the workflow, causing logs to not stream in real-time during resume.

## Root Cause
The `/approve/{thread_id}` endpoint was fetching the `broadcast` flag from:
```python
state = await app.aget_state(config)
broadcast = state.values.get("_broadcast", False)
```

This approach has issues:
1. **Checkpoint load dependency** - Requires loading the full checkpoint state before knowing whether to enable broadcast
2. **Not available in API context** - The `_broadcast` flag is in workflow state, not readily accessible from the API endpoint
3. **Server restart issues** - If checkpoint is not yet loaded from Redis/PostgreSQL, the flag would be `False`

## Solution Architecture

Use a **dual-storage approach** for the broadcast setting:

1. **In `run_metadata.metadata` JSONB** (Database)
   - Used by the `/approve` endpoint to restore log context in the background task
   - Persists across server restarts
   - Accessible without loading workflow state

2. **In workflow `state["_broadcast"]`** (Workflow State)
   - Used by workflow nodes (`autonomous_planner`, `skilled_executor`) to restore log context
   - Persisted in checkpoints (Redis/PostgreSQL)
   - Travels with the workflow state throughout execution

### Data Flow

#### Initial Run (`/start`)
```
User Request (broadcast=true)
  ↓
_save_run_metadata(..., broadcast=true)  → DB: run_metadata.metadata = {"broadcast": true}
  ↓
initial_state["_broadcast"] = true      → State: persisted in checkpoint
```

#### HITL Pause
```
Workflow hits HITL
  ↓
Checkpoint saved (includes state["_broadcast"] = true)
  ↓
Status set to "paused"
```

#### HITL Resume (`/approve`)
```
/approve/{thread_id} called
  ↓
metadata = _get_run_metadata(thread_id)  → Fetch from DB
broadcast = metadata["metadata"]["broadcast"]
  ↓
Background Task: set_log_context(thread_id, broadcast=broadcast)
  ↓
app.astream(None, config)  → Load checkpoint
  ↓
Node executes: autonomous_planner/skilled_executor
  ↓
broadcast = state.get("_broadcast", False)  → From checkpoint state
set_log_context(thread_id, broadcast=broadcast)  → Restore in node
```

### Why Both Storage Locations?

| Storage Location | Purpose | When Used | Survives Server Restart |
|-----------------|---------|-----------|------------------------|
| `run_metadata.metadata` | API-level broadcast control | `/approve` background task initialization | ✅ Yes |
| `state["_broadcast"]` | Node-level broadcast restoration | Within workflow nodes during execution | ✅ Yes (in checkpoint) |

Both are necessary because:
- The API endpoint needs to know the broadcast setting **before** spawning the background task
- The workflow nodes need to restore the broadcast context **during** execution
- Each operates in a different scope (API context vs. workflow execution context)

### Changes Made

#### 1. Updated `_save_run_metadata` function
Added `broadcast` parameter and store it in metadata JSONB:

```python
async def _save_run_metadata(
    # ... existing parameters ...
    broadcast: bool = False,  # NEW: Add broadcast parameter
):
    # Build metadata JSONB with callback_url and broadcast flag
    metadata = {}
    if callback_url:
        metadata['callback_url'] = callback_url
    metadata['broadcast'] = broadcast  # Store broadcast setting
```

#### 2. Updated `/start` endpoint
Pass `broadcast` when saving metadata:

```python
await _save_run_metadata(
    req.thread_id,
    req.sop,
    req.initial_data or {},
    run_name=run_name,
    user_id=current_user.id,
    workspace_id=workspace_id,
    llm_model=req.llm_model,
    callback_url=req.callback_url,
    broadcast=req.broadcast,  # Store broadcast setting
)
```

#### 3. Updated `/rerun` endpoint
Pass `broadcast` when saving rerun metadata:

```python
await _save_run_metadata(
    new_thread_id,
    metadata["sop"],
    metadata["initial_data"],
    parent_thread_id=thread_id,
    run_name=new_run_name,
    user_id=current_user.id,
    workspace_id=workspace.id,
    llm_model=metadata.get("llm_model"),
    callback_url=req.callback_url,
    broadcast=req.broadcast,  # Store broadcast setting
)
```

#### 4. Updated `/approve/{thread_id}` endpoint
Retrieve `broadcast` from `run_metadata` instead of state:

```python
# OLD (unreliable):
state = await app.aget_state(config)
broadcast = state.values.get("_broadcast", False)

# NEW (persistent):
metadata = await _get_run_metadata(thread_id)
broadcast = metadata.get("metadata", {}).get("broadcast", False)
```

## Benefits

1. **Server restart resilience**: Broadcast setting survives server restarts
2. **Correctness**: Always retrieves the original run's configuration
3. **Consistency**: Same source of truth for initial run and resume
4. **Simplicity**: No dependency on workflow state structure

## Data Structure

### run_metadata table schema
```sql
CREATE TABLE run_metadata (
    thread_id TEXT PRIMARY KEY,
    run_name TEXT,
    sop TEXT,
    initial_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    parent_thread_id TEXT,
    rerun_count INTEGER DEFAULT 0,
    status TEXT,
    error_message TEXT,
    failed_skill TEXT,
    completed_at TIMESTAMP,
    user_id UUID,
    workspace_id UUID,
    llm_model TEXT,
    metadata JSONB  -- Contains: {"callback_url": "...", "broadcast": true/false}
);
```

### Example metadata JSONB
```json
{
  "callback_url": "https://example.com/webhook",
  "broadcast": true
}
```

## Testing

### Test Case 1: Normal resume
1. Start a workflow with `broadcast=true`
2. Hit HITL pause
3. Resume via `/approve/{thread_id}`
4. **Expected**: Logs stream in real-time during resume

### Test Case 2: Resume after server restart
1. Start a workflow with `broadcast=true`
2. Hit HITL pause
3. **Restart the server**
4. Resume via `/approve/{thread_id}`
5. **Expected**: Logs still stream in real-time (broadcast setting restored from DB)

### Test Case 3: Rerun with different broadcast setting
1. Complete a workflow with `broadcast=false`
2. Rerun with `broadcast=true`
3. Hit HITL pause
4. Resume
5. **Expected**: Rerun uses `broadcast=true` (not inherited from parent)

## Related Documentation
- `HITL_COMPLETE_GUIDE.md` - Comprehensive HITL workflow documentation
- `HITL_RESUME_FIX.md` - Original context variable propagation fix
