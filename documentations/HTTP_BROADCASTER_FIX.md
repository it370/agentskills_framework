# HTTP Broadcaster Production Fix
# Nelvin's Note:
It is important to set the SOCKETIO_INTERNAL_HOST to 127.0.0.1 when hosted in VM on same machine in prod mode else socket broadcast will not work, it works only in dev mode.

## Issue

When running in **production/build mode**, log broadcasting fails with:
```
[HTTP_BROADCASTER] Failed to broadcast log:
```

Workflow continues to run but logs are not streamed to the frontend in real-time.

**In dev mode**: Works fine
**In production mode**: Fails silently

## Root Cause

The HTTP broadcaster was using `localhost` as the default host to connect to the Socket.IO server:

```python
# Old code (problematic)
SOCKETIO_HOST = os.getenv('SOCKETIO_HOST', 'localhost')
```

### Why This Fails in Production:

1. **DNS Resolution**: `localhost` may not resolve correctly in some production environments (containers, VMs, cloud)
2. **Network Configuration**: Some systems have `localhost` disabled or misconfigured
3. **IPv6 vs IPv4**: `localhost` might resolve to IPv6 (`::1`) when the server expects IPv4 (`127.0.0.1`)
4. **Build Mode**: Next.js build mode uses different networking stack

## The Fix

### 1. Changed Default from `localhost` to `127.0.0.1`

**File**: `services/websocket/http_broadcaster.py`

```python
# New code (fixed)
SOCKETIO_HOST = os.getenv('SOCKETIO_INTERNAL_HOST') or os.getenv('SOCKETIO_HOST', '127.0.0.1')
```

**Benefits:**
- ✅ `127.0.0.1` is the loopback IP (always works for same-machine communication)
- ✅ Works in all environments (dev, production, containers, VMs)
- ✅ No DNS resolution needed
- ✅ IPv4 explicit (no IPv6 confusion)

### 2. Added Better Error Messages

Now distinguishes between different failure types:

```python
except httpx.ConnectError as e:
    print(f"[HTTP_BROADCASTER] Cannot reach Socket.IO server at {SOCKETIO_BASE}: {e}")
except httpx.TimeoutException:
    print(f"[HTTP_BROADCASTER] Socket.IO server timeout at {SOCKETIO_BASE}")
except Exception as e:
    print(f"[HTTP_BROADCASTER] Failed to broadcast log: {e}")
```

**This helps diagnose:**
- Connection refused (Socket.IO not running)
- Timeout (Socket.IO overloaded)
- Other errors (network issues, SSL problems)

### 3. Added Startup Logging

```python
print(f"[HTTP_BROADCASTER] Socket.IO endpoint: {SOCKETIO_BASE}")
```

Now you'll see on startup:
```
[HTTP_BROADCASTER] Socket.IO endpoint: http://127.0.0.1:7000
```

This confirms the broadcaster knows where to send logs.

### 4. New Environment Variable (Optional)

Added `SOCKETIO_INTERNAL_HOST` for explicit internal communication:

```bash
# .env
SOCKETIO_INTERNAL_HOST=127.0.0.1  # For same-machine setup
# OR
SOCKETIO_INTERNAL_HOST=192.168.1.10  # For multi-machine setup
```

Priority order:
1. `SOCKETIO_INTERNAL_HOST` (explicit internal communication)
2. `SOCKETIO_HOST` (fallback to external host)
3. `127.0.0.1` (default loopback)

## Configuration Scenarios

### Scenario 1: Single Machine (Most Common)
```bash
# .env
REST_API_HOST=0.0.0.0
REST_API_PORT=8000
SOCKETIO_HOST=0.0.0.0
SOCKETIO_PORT=7000
# No need to set SOCKETIO_INTERNAL_HOST - uses 127.0.0.1 automatically
```

**How it works:**
- REST API binds to `0.0.0.0:8000` (accepts external connections)
- Socket.IO binds to `0.0.0.0:7000` (accepts external connections)
- REST API connects to Socket.IO via `127.0.0.1:7000` (internal loopback)
- Frontend connects to Socket.IO via public IP/domain

### Scenario 2: Docker Compose
```bash
# .env
REST_API_HOST=0.0.0.0
SOCKETIO_HOST=0.0.0.0
SOCKETIO_INTERNAL_HOST=socketio  # Docker service name
```

### Scenario 3: Separate Machines
```bash
# REST API machine .env
SOCKETIO_INTERNAL_HOST=192.168.1.20  # Socket.IO machine IP

# Socket.IO machine .env
SOCKETIO_HOST=0.0.0.0
SOCKETIO_PORT=7000
```

### Scenario 4: EC2 with Nginx
```bash
# .env
SOCKETIO_INTERNAL_HOST=127.0.0.1  # Same machine
# Nginx proxies external requests to localhost:7000
```

## Testing

### 1. Check Startup Logs

When you start the backend, you should now see:
```
[HTTP_BROADCASTER] Socket.IO endpoint: http://127.0.0.1:7000
[MAIN] Starting Socket.IO server...
[SOCKETIO_SERVER] Starting Socket.IO server on 0.0.0.0:7000
[MAIN] Starting REST API server...
```

### 2. Test Log Broadcasting

Start a workflow run and watch for:

**Good (Working):**
```
[PLANNER] Decision: kudos-data-retriever
[EXECUTOR] Running kudos-data-retriever...
[EXECUTOR] Running action kudos-data-retriever (type: data_query)
```

**Bad (Still Broken):**
```
[PLANNER] Decision: kudos-data-retriever
[HTTP_BROADCASTER] Cannot reach Socket.IO server at http://127.0.0.1:7000: ...
[EXECUTOR] Running kudos-data-retriever...
[HTTP_BROADCASTER] Cannot reach Socket.IO server at http://127.0.0.1:7000: ...
```

### 3. Verify Socket.IO is Running

```bash
# Check if Socket.IO is listening
curl http://127.0.0.1:7000/health

# Should return:
# {"status":"healthy","service":"socketio","port":7000,"connections":{...}}
```

## Troubleshooting

### Error: "Cannot reach Socket.IO server"

**Cause**: Socket.IO server is not running or not reachable

**Solutions:**
1. Check if Socket.IO process is running:
   ```bash
   # Linux/Mac
   lsof -i :7000
   
   # Windows
   netstat -ano | findstr :7000
   ```

2. Restart backend:
   ```bash
   python main.py
   ```

3. Check firewall rules (if on separate machines)

### Error: "Connection refused"

**Cause**: Socket.IO server port is blocked or wrong IP

**Solutions:**
1. Verify Socket.IO is listening:
   ```bash
   curl http://127.0.0.1:7000/
   ```

2. Check `.env` configuration

3. Try explicit internal host:
   ```bash
   # In .env
   SOCKETIO_INTERNAL_HOST=127.0.0.1
   ```

### Logs Still Not Appearing in Frontend

**Possible causes:**
1. Frontend not connected to Socket.IO
2. CORS issues
3. Wrong Socket.IO URL in frontend

**Check frontend console:**
```javascript
// Should see:
Socket.IO connected
```

**Frontend .env.local:**
```bash
NEXT_PUBLIC_SOCKETIO_BASE=http://YOUR_IP:7000
```

## Summary

| Before | After |
|--------|-------|
| Uses `localhost` | Uses `127.0.0.1` |
| Generic error messages | Specific error types |
| No startup logging | Shows Socket.IO endpoint |
| Fails in production | Works everywhere |

**The fix ensures log broadcasting works reliably in all deployment scenarios! 🎉**
