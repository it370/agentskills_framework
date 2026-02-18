# Checkpoint Flush Error Flow - Before vs After

## ❌ BEFORE (Problem State)

```
Workflow Execution
       |
       v
Checkpoint contains NaN value
       |
       v
Save to Redis ✅ (no validation)
       |
       v
Workflow completes
       |
       v
flush_to_postgres() called
       |
       v
JSON serialization FAILS 💥
ValueError: Out of range float values are not JSON compliant: nan
       |
       v
Exception caught silently 🤫
       |
       v
User sees: "Workflow completed" ✓
       |
       v
User tries to view logs... 
       |
       v
❌ NO LOGS AVAILABLE
❌ NO ERROR MESSAGE
❌ USER IS BLIND
👨‍💻 Admin forced to troubleshoot
```

## ✅ AFTER (Fixed State)

```
Workflow Execution
       |
       v
Checkpoint contains NaN value
       |
       v
sanitize_for_json() ✨
NaN → None (null)
       |
       v
Save to Redis ✅ (sanitized data)
       |
       v
Workflow completes
       |
       v
flush_to_postgres() called
       |
       v
sanitize_for_json() again ✨ (double-check)
       |
       v
JSON serialization SUCCESS ✅
       |
       v
PostgreSQL INSERT SUCCESS ✅
       |
       v
User sees: "Workflow completed" ✓
       |
       v
User views logs...
       |
       v
✅ LOGS AVAILABLE
✅ EXECUTION HISTORY PRESERVED
✅ USER CAN SEE EVERYTHING
```

## 🚨 Alternative Path: If Flush Still Fails

```
flush_to_postgres() called
       |
       v
Unexpected error occurs 💥
(network issue, DB down, etc.)
       |
       v
Exception caught 🎯
       |
       |-----> Log to console
       |-----> emit_log(level="ERROR") 
       |-----> broadcast_run_event() 📡
       |
       v
User's UI receives event 🖥️
       |
       v
⚠️ WARNING/CRITICAL Banner shown
       |
       v
✅ USER AWARE OF PROBLEM
✅ ACTIONABLE ERROR MESSAGE
✅ NO SILENT FAILURE
👨‍💻 Admin gets context for troubleshooting
```

## Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Data Quality** | NaN values cause crashes | Sanitized to None/null |
| **User Awareness** | Silent failure | Real-time notification |
| **Log Availability** | Lost forever | Preserved in buffer |
| **Admin T/S** | Blind debugging | Error context provided |
| **Error Handling** | Exception swallowed | Multi-layer detection |
| **UX** | Confusing (no feedback) | Clear (error banners) |

## Defense Layers

1. **Layer 1**: Sanitize at Redis write (prevents storage of bad data)
2. **Layer 2**: Sanitize at PostgreSQL write (double-check)
3. **Layer 3**: Check return value (detect soft failures)
4. **Layer 4**: Catch exceptions (detect hard failures)
5. **Layer 5**: Broadcast to UI (notify user)
6. **Layer 6**: Console logging (admin visibility)

**Result**: Users are NEVER left blind, regardless of failure mode.
