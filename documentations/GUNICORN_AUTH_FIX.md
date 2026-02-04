# Gunicorn/Hypercorn Worker Process Issue - AuthContext Fix

## Problem
When using Gunicorn (Linux/Mac) or Hypercorn (Windows) in production, the `AuthContext` singleton initialized in the parent/master process doesn't carry over to worker processes, causing credential-based skills to fail with:

```
RuntimeError: user_context required for secure credentials. Either:
  1. Pass user_context in inputs, or
  2. Initialize global auth at startup:
     from services.credentials import AuthContext, get_system_user
     AuthContext.initialize(get_system_user())
```

Even though the logs show `[AUTH] Initialized global auth context for user: system` in the parent process.

## Root Cause

### Gunicorn (Linux/Mac)
- Gunicorn uses process forking to create worker processes
- Python class variables (like `AuthContext._current_user`) are not guaranteed to persist correctly across fork boundaries
- When `preload_app = True`, the app is loaded in master process, then workers are forked
- Worker processes end up with `AuthContext._current_user = None` despite initialization in master

### Hypercorn (Windows via subprocess)
- `production_server.py` spawns Hypercorn as a subprocess: `subprocess.run(["hypercorn", "api:api", ...])`
- This creates a **completely new Python process** that loads the FastAPI app fresh
- AuthContext initialized in the parent `production_server.py` process doesn't carry over to the child Hypercorn process
- Each Hypercorn worker loads `api:api` without AuthContext being initialized

## Solution Applied

### PRIMARY FIX: Initialize AuthContext in API Module (All Platforms)
Added AuthContext initialization directly in `api/main.py` when the module is loaded:

```python
# In api/main.py, right after FastAPI app creation
api = FastAPI(title="Agentic SOP Orchestrator")

# Track background workflow tasks so we can cancel them.
RUN_TASKS: Dict[str, asyncio.Task] = {}

# Initialize AuthContext on API module load (for Hypercorn/Waitress workers)
# This ensures each worker process has AuthContext properly initialized
try:
    from services.credentials import AuthContext
    if not AuthContext.is_initialized():
        auth = AuthContext.initialize_from_env()
        print(f"[API] Initialized AuthContext for user: {auth.get_current_user().user_id}")
except Exception as e:
    print(f"[API] WARNING: Could not initialize AuthContext: {e}")
    print(f"[API] Credential-based skills may fail without user_context in inputs")
```

**Why this works:**
- When Hypercorn/Gunicorn workers load `api:api`, they import the `api.main` module
- The initialization code runs during module import, ensuring AuthContext is set up in each worker
- Works for all ASGI servers (Uvicorn, Hypercorn, Gunicorn+Uvicorn workers)
- Works whether server is started directly or via subprocess

### SECONDARY FIX: Gunicorn Configuration (Linux/Mac only)
For Gunicorn deployments, also updated `gunicorn.conf.py`:

1. **Set preload_app = False:**
```python
# Preload app for better memory usage
# NOTE: Set to False if you have issues with class variables/singletons not being
# properly initialized in worker processes (e.g., AuthContext)
preload_app = False
```

2. **Enhanced post_fork hook:**
```python
def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"[GUNICORN] Worker spawned (pid: {worker.pid})")
    
    # CRITICAL: Reset and re-initialize auth context per worker
    # Class variables from master process may not carry over properly after fork
    try:
        from services.credentials import AuthContext
        
        # Reset the auth context to ensure clean state in worker
        AuthContext.reset()
        
        # Re-initialize for this worker
        auth = AuthContext.initialize_from_env()
        print(f"[WORKER {worker.pid}] Auth context initialized for user: {auth.get_current_user().user_id}")
    except Exception as e:
        print(f"[WORKER {worker.pid}] WARNING: Could not initialize auth context: {e}")
```

## Verification
After applying the fix, you should see:

### Uvicorn (Development)
```
[AUTH] Initialized global auth context for user: system  # from main.py
[API] Initialized AuthContext for user: system            # from api/main.py (may be skipped if already initialized)
```

### Hypercorn (Windows Production)
```
[AUTH] Initialized global auth context for user: system  # from production_server.py parent
[API] Initialized AuthContext for user: system            # from api/main.py in Hypercorn worker
```

### Gunicorn (Linux/Mac Production)
```
[WORKER 12345] Auth context initialized for user: system  # from post_fork hook
[API] Initialized AuthContext for user: system            # from api/main.py (may be skipped if already initialized)
```

If you see the WARNING message, check:
1. Environment variables are properly loaded in worker process
2. The `services.credentials` module is importable
3. No import errors in the credentials system

## Testing
To test if the fix works:

1. **Restart your production server:**
   - Windows: `.\start-production.bat`
   - Linux/Mac: `./start-production.sh`

2. **Check logs for AuthContext initialization:**
   Look for `[API] Initialized AuthContext for user: system` from each worker

3. **Execute a skill that uses credentials:**
   Should work without the `user_context required` error

4. **Monitor for errors:**
   If still failing, check which worker/thread handled the request and review its initialization logs

## Alternative: Per-Request User Context
If issues persist, consider passing user context explicitly per request by modifying the API to inject user context into workflow inputs based on the authenticated user.

## Date Applied
2026-02-05

## Files Modified
- `api/main.py` - Primary fix (initializes AuthContext on module load)
- `gunicorn.conf.py` - Secondary fix for Gunicorn deployments
- `testscripts/diagnose_auth_context.py` - Diagnostic tool created
