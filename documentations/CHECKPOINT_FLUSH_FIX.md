# Critical Fix: Checkpoint Flush Error Handling & User Notification

## Problem Statement

**Critical Issue**: When checkpoint data flush to PostgreSQL fails (e.g., due to NaN/Infinity values in checkpoint data), the application silently fails without crashing. This leaves users completely blind because:

1. ❌ Live logs stop streaming (they're stored in Redis but never reach PostgreSQL)
2. ❌ Thread logs become unavailable (checkpoint flush failed)
3. ❌ Users have no indication that something went wrong
4. ❌ Admins are forced to troubleshoot blindly

### Original Error
```
ValueError: Out of range float values are not JSON compliant: nan
when serializing list item 0
when serializing dict item 'neighbor_bounding_box'
when serializing dict item 'data_store'
when serializing dict item 'channel_values'
when serializing dict item 'checkpoint'

psycopg.errors.InvalidTextRepresentation: invalid input syntax for type json
DETAIL:  Token "NaN" is invalid.
CONTEXT:  JSON data, line 1: ...487228814582)))"}], "neighbor_bounding_box": [NaN...
```

## Solution Overview

This fix implements a **multi-layered approach** to ensure users are NEVER left blind:

### 1. **Data Sanitization** (Prevention)
- Sanitize checkpoint data before JSON serialization
- Convert NaN, Infinity, -Infinity → None (null in JSON)
- Works recursively on nested structures (dicts, lists)

### 2. **Error Detection** (Monitoring)
- Check `flush_to_postgres()` return value
- Distinguish between soft failures and critical errors

### 3. **User Notification** (Visibility)
- Broadcast error messages to user's UI via WebSocket
- Use existing `broadcast_run_event()` infrastructure
- Provide actionable error messages with severity levels

## Changes Made

### File 1: `services/checkpoint_buffer.py`

#### Added `sanitize_for_json()` Function
```python
def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize data structure to be JSON-compliant.
    
    Converts NaN, Infinity, and -Infinity to None to prevent JSON serialization errors.
    PostgreSQL JSONB also rejects NaN/Infinity values.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None  # Convert NaN/Inf to null in JSON
        return obj
    else:
        return obj
```

#### Updated `add_checkpoint()` Method
- Sanitize checkpoint data **before** storing in Redis
- Prevents NaN values from ever entering the buffer

```python
# Sanitize data to prevent NaN/Infinity JSON errors
sanitized_data = sanitize_for_json(checkpoint_data)

# Serialize checkpoint
checkpoint_json = json.dumps(sanitized_data)
```

#### Updated `flush_to_postgres()` Method
- Added defensive sanitization before PostgreSQL insert
- Double-layer protection (Redis + PostgreSQL)

```python
# Sanitize checkpoint and metadata before JSON serialization
sanitized_checkpoint = sanitize_for_json(checkpoint)
sanitized_metadata = sanitize_for_json(metadata)

cur.execute("""...""", (
    thread_id,
    checkpoint_ns,
    checkpoint_id,
    parent_checkpoint_id,
    'checkpoint',
    json.dumps(sanitized_checkpoint),
    json.dumps(sanitized_metadata)
))
```

### File 2: `api/main.py`

#### Added Error Broadcasting to Users

**When checkpoint flush fails (soft failure):**
```python
if not success:
    error_msg = (
        "⚠️ WARNING: Failed to save execution logs to database. "
        "The workflow completed but logs may be incomplete. "
        "Please contact support if you need detailed execution history."
    )
    emit_log(f"[API] {error_msg}", thread_id=thread_id, level="ERROR")
    
    # Broadcast error notification to user's UI
    await broadcast_run_event({
        "thread_id": thread_id,
        "type": "checkpoint_flush_error",
        "message": error_msg,
        "severity": "warning",
        "timestamp": datetime.utcnow().isoformat()
    })
```

**When checkpoint flush crashes (critical failure):**
```python
except Exception as e:
    error_msg = (
        f"⚠️ CRITICAL ERROR: Checkpoint flush process failed for thread {thread_id}. "
        f"Logs and execution history may not be saved. Error: {str(e)[:200]}"
    )
    emit_log(f"[API] {error_msg}", thread_id=thread_id, level="ERROR")
    
    # Broadcast critical error to user's UI
    await broadcast_run_event({
        "thread_id": thread_id,
        "type": "checkpoint_flush_critical_error",
        "message": (
            "⚠️ CRITICAL: Failed to save execution data. "
            "Please contact support immediately. This workflow's logs may be lost."
        ),
        "severity": "critical",
        "error_details": str(e)[:500],
        "timestamp": datetime.utcnow().isoformat()
    })
```

## Testing

### Test Script: `tests/test_checkpoint_sanitization.py`

Created comprehensive test covering:
- ✅ Simple NaN values
- ✅ Infinity values
- ✅ Negative Infinity values
- ✅ Nested structures (mimics actual error case)
- ✅ Mixed valid/invalid values
- ✅ Normal values preservation

**Run the tests:**
```bash
# From project root
conda run -n clearstar python tests/test_checkpoint_sanitization.py

# Or with regular python
python tests/test_checkpoint_sanitization.py
```

**All tests passed!** ✅

```
✅ Test 4: Nested structure with NaN (actual error case)
   Input:  {'checkpoint': {'channel_values': {'data_store': {'neighbor_bounding_box': [nan, nan, 123.45, inf]}}}}
   Output: {'checkpoint': {'channel_values': {'data_store': {'neighbor_bounding_box': [None, None, 123.45, None]}}}}
   JSON:   {"checkpoint": {"channel_values": {"data_store": {"neighbor_bounding_box": [null, null, 123.45, null]}}}}
```

## Benefits

### For Users 👥
1. **Visibility**: Always notified when log persistence fails
2. **Actionable**: Clear error messages indicating what happened
3. **Trustworthy**: No silent failures - users know the system status

### For Admins 🔧
1. **Faster T/S**: Error messages include context (thread_id, error type)
2. **Proactive**: Errors broadcast in real-time, not discovered later
3. **Traceable**: Errors logged to console and database (if available)

### For System Health 💚
1. **Resilient**: Prevents crashes from NaN/Infinity values
2. **Observable**: All failure modes are visible
3. **Graceful**: Workflow completes even if log persistence fails

## Error Severity Levels

| Severity | Trigger | User Message | Action Required |
|----------|---------|--------------|-----------------|
| **warning** | `flush_to_postgres()` returns `False` | "Failed to save execution logs to database" | Contact support if detailed history needed |
| **critical** | Exception during checkpoint flush | "Failed to save execution data" | Contact support immediately |

## UI Integration Requirements

The frontend should handle these new event types:

### Event Type 1: `checkpoint_flush_error`
```typescript
{
  thread_id: string;
  type: "checkpoint_flush_error";
  message: string;
  severity: "warning";
  timestamp: string;
}
```

**Suggested UI**: Yellow warning banner at top of log viewer

### Event Type 2: `checkpoint_flush_critical_error`
```typescript
{
  thread_id: string;
  type: "checkpoint_flush_critical_error";
  message: string;
  severity: "critical";
  error_details: string;
  timestamp: string;
}
```

**Suggested UI**: Red critical error banner with "Contact Support" button

## Backwards Compatibility

✅ **Fully backwards compatible**
- New fields only added, no breaking changes
- Existing event types unchanged
- Sanitization is transparent (converts NaN → null)
- Frontend can ignore new event types if not yet implemented

## Future Improvements

1. **Retry Logic**: Implement exponential backoff for transient failures
2. **Fallback Storage**: Store failed checkpoints in alternative storage (S3, file system)
3. **Alerting**: Send alerts to admin dashboard/email on repeated failures
4. **Metrics**: Track checkpoint flush success/failure rates
5. **Debug Mode**: Add verbose logging to capture pre-sanitization values

## Root Cause Analysis

The original error occurred because:
1. Some skill execution produced NaN values in `neighbor_bounding_box` field
2. NaN values are not JSON-compliant per RFC 8259
3. PostgreSQL JSONB column rejects NaN tokens
4. Checkpoint flush failed silently with exception caught but not reported to users

**This fix addresses all layers of the problem: prevention (sanitization), detection (return value checking), and notification (user broadcasts).**

## Deployment Notes

1. ✅ No database migrations required
2. ✅ No environment variable changes required
3. ✅ No dependency updates required
4. ⚠️ Consider deploying frontend updates to handle new event types
5. ✅ Test script included for verification: `tests/test_checkpoint_sanitization.py`

---

**Status**: ✅ Complete and tested
**Priority**: CRITICAL FIX
**Risk**: Low (backwards compatible, defensive programming)
