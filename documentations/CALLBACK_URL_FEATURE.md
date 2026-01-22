# Callback URL Feature

## Overview
This feature allows users to specify a `callback_url` parameter when starting or rerunning a workflow. When the run completes (regardless of success or failure), the system will automatically invoke the callback URL with the complete run metadata as the payload.

## Implementation Details

### 1. API Changes

#### StartRequest Model
Added optional `callback_url` field:
```python
class StartRequest(BaseModel):
    thread_id: str
    sop: str
    initial_data: Optional[Dict[str, Any]] = None
    run_name: Optional[str] = None
    ack_key: Optional[str] = None
    workspace_id: Optional[str] = None
    llm_model: Optional[str] = None
    callback_url: Optional[str] = None  # NEW: Webhook URL to call when run completes
```

#### RerunRequest Model
Added optional `callback_url` field:
```python
class RerunRequest(BaseModel):
    ack_key: Optional[str] = None
    callback_url: Optional[str] = None  # NEW: Webhook URL to call when run completes
```

### 2. Database Storage

The `callback_url` is stored in the existing `metadata` JSONB column in the `run_metadata` table:
```json
{
  "callback_url": "https://your-webhook-endpoint.com/callback"
}
```

**No database migration required** - we're using the existing `metadata` column that's already defined in the schema.

### 3. Callback Invocation

#### When is the callback invoked?
The callback is invoked in the following scenarios:
1. **Workflow completes successfully** - status: `completed`
2. **Workflow fails** - status: `error` or `failed`
3. **Workflow is cancelled** - status: `cancelled`

#### What data is sent?
The callback receives essential run metadata as a JSON payload (optimized for size and speed):
```json
{
  "thread_id": "thread_uuid",
  "status": "completed",
  "error_message": null,
  "run_name": "My Workflow Run",
  "created_at": "2026-01-22T10:30:00Z",
  "llm_model": "gpt-4",
  "failed_skill": null,
  "completed_at": "2026-01-22T10:35:00Z"
}
```

**Note:** The payload is intentionally minimal to reduce network overhead and improve performance. If you need additional data (SOP, initial_data, workspace_id, etc.), you can query the `/admin/runs/{thread_id}/metadata` endpoint using the `thread_id` from the callback.

### 4. Implementation Functions

#### `_save_run_metadata()`
Updated to accept and store `callback_url` parameter in the metadata JSONB field.

#### `_get_run_metadata_for_callback(thread_id: str)`
New optimized async function that:
1. Queries only essential fields from the database (faster query)
2. Returns minimal payload: thread_id, status, error_message, run_name, created_at, llm_model, failed_skill, completed_at
3. Extracts callback_url from metadata JSONB field

#### `_invoke_callback(thread_id: str)`
New async function that:
1. Fetches minimal run metadata from the database (optimized query)
2. Checks if `callback_url` is configured in the metadata
3. If configured, makes an HTTP POST request to the callback URL with minimal payload
4. Logs success or failure (non-blocking - errors are logged but don't affect workflow)

#### `_run_workflow()`
Updated to invoke the callback after status updates in the following cases:
- After workflow completes successfully
- After workflow fails
- After workflow is cancelled
- After workflow encounters an error

### 5. Error Handling

- Callback invocation is **fire-and-forget** (non-blocking) - workflow doesn't wait for callback completion
- Callback has a 30-second timeout
- HTTP errors are logged but don't affect the workflow
- If the callback fails, it's logged to both the console and the run logs
- The callback is only invoked if `callback_url` is present in the metadata

### 6. Performance Optimizations

- **Fire-and-forget**: Callback invocation doesn't block workflow completion (async background task)
- **Single query approach**: Fetches all callback fields in one query (optimized for high callback usage)
- **Minimal payload**: Only 8 fields sent to reduce network overhead
- **Database indexes**: GIN index on metadata JSONB column for fast lookups
- **Partial index**: Expression index on `callback_url` field for even faster checks
- **Connection pooling**: Reuses database connections for better performance

## Usage Examples

### Example 1: Start a workflow with callback
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "thread_id": "thread_123",
    "sop": "Process customer order",
    "initial_data": {"order_id": "12345"},
    "callback_url": "https://myapp.com/webhooks/workflow-complete"
  }'
```

### Example 2: Rerun a workflow with callback
```bash
curl -X POST http://localhost:8000/rerun/thread_123 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "callback_url": "https://myapp.com/webhooks/rerun-complete"
  }'
```

### Example 3: Receiving the callback
Your webhook endpoint will receive a POST request with the run metadata:

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhooks/workflow-complete")
async def workflow_callback(request: Request):
    payload = await request.json()
    
    # Extract key information from minimal payload
    thread_id = payload["thread_id"]
    status = payload["status"]
    error_message = payload.get("error_message")
    
    if status == "completed":
        print(f"Workflow {thread_id} completed successfully!")
        # Process successful completion
    elif status == "error":
        print(f"Workflow {thread_id} failed: {error_message}")
        # Handle failure
    
    # If you need more details (SOP, initial_data, etc.):
    # Make a GET request to /admin/runs/{thread_id}/metadata
    
    return {"status": "received"}
```

## Testing

To test the callback feature:

1. Start a test workflow with a callback URL pointing to a webhook testing service (e.g., webhook.site)
2. Monitor the workflow execution
3. Verify the callback is invoked when the workflow completes
4. Check that the payload contains the complete run metadata

## Notes

- The callback is **fire-and-forget** (asynchronous) - workflow completes immediately without waiting for callback
- The callback URL is stored per-run, so different runs can have different callbacks
- For reruns, you can specify a different callback_url or omit it to not use a callback
- The callback receives the **latest** metadata snapshot after the status update
- The payload is **minimal** (8 fields only) for performance - query the full metadata endpoint if you need more details
- Callback invocation is logged in the run logs for debugging
- Callback failures don't affect workflow execution or completion
