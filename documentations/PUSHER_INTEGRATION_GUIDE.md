# Pusher Integration Guide

## Overview

The AgentSkills Framework now uses **Pusher Channels** for real-time log streaming and admin event broadcasting, replacing the self-hosted Socket.IO server.

### Benefits
- ✅ **No infrastructure management** - Pusher handles all WebSocket infrastructure
- ✅ **Better reliability** - Enterprise-grade uptime and scaling
- ✅ **Automatic reconnection** - Built-in connection recovery
- ✅ **Simple pricing** - Free tier: 200K messages/day, 100 concurrent connections
- ✅ **Future-ready** - Prepared for Ably fallback when limits reached

---

## Architecture

### Backend (Python)
```
log_stream.py / admin_events.py
          ↓
services/websocket/broadcaster_manager.py
          ↓
services/websocket/pusher_broadcaster.py
          ↓
    Pusher API (HTTPS)
          ↓
    Pusher Channels
```

### Frontend (Next.js)
```
React Components
          ↓
admin-ui/src/lib/api.ts
          ↓
   pusher-js library
          ↓
Pusher WebSocket (wss://)
```

### Message Flow
1. Backend Python code calls `broadcast_log()` or `broadcast_admin_event()`
2. Broadcaster manager routes to Pusher broadcaster
3. Pusher broadcaster sends HTTP POST to Pusher API
4. Pusher distributes via WebSocket to all subscribed clients
5. Frontend receives real-time updates

---

## Setup Instructions

### Step 1: Get Pusher Credentials

1. Sign up at [https://pusher.com](https://pusher.com)
2. Create a new Channels app
3. Choose cluster closest to your users (e.g., `ap2` for Asia Pacific)
4. Get your credentials from the "App Keys" tab:
   - `app_id`
   - `key`
   - `secret`
   - `cluster`

### Step 2: Backend Configuration

Add to your `.env` file:

```bash
# Pusher Configuration
PUSHER_APP_ID=your_app_id_here
PUSHER_KEY=your_key_here
PUSHER_SECRET=your_secret_here
PUSHER_CLUSTER=ap2  # or your chosen cluster
```

**Security Note**: Keep `PUSHER_SECRET` confidential - it's used for server-side signing.

### Step 3: Install Backend Dependencies

```bash
# Activate clearstar conda environment
conda activate clearstar

# Install pusher library
pip install pusher

# Or install all requirements
pip install -r requirements.txt
```

### Step 4: Frontend Configuration

Create/update `admin-ui/.env.local`:

```bash
# Pusher Configuration
NEXT_PUBLIC_PUSHER_KEY=your_key_here
NEXT_PUBLIC_PUSHER_CLUSTER=ap2
NEXT_PUBLIC_USE_PUSHER=true

# API Configuration
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

**Note**: Only `PUSHER_KEY` is exposed to frontend (public key), `PUSHER_SECRET` stays server-side.

### Step 5: Install Frontend Dependencies

```bash
cd admin-ui
npm install
```

This will install `pusher-js` (already added to `package.json`).

### Step 6: Start the Services

```bash
# Backend (from project root)
python main.py

# Frontend (from admin-ui folder)
cd admin-ui
npm run dev
```

---

## Channels and Events

### Channel: `logs`
- **Purpose**: Real-time log streaming from workflow execution
- **Event**: `log`
- **Payload**:
  ```json
  {
    "text": "Log message text",
    "thread_id": "workflow-thread-id",
    "level": "INFO",
    "timestamp": "2026-01-15T10:30:00.000Z"
  }
  ```

### Channel: `admin`
- **Purpose**: Workflow status updates and admin events
- **Event**: `admin_event`
- **Payload**:
  ```json
  {
    "type": "run_event",
    "data": {
      "thread_id": "workflow-thread-id",
      "event_type": "checkpoint_saved",
      "checkpoint_id": "...",
      "status": "running"
    }
  }
  ```

---

## Rate Limit Detection

The Pusher broadcaster automatically detects rate limits and disables itself for the session:

### How It Works
1. Pusher returns HTTP 402 (Payment Required) when limit reached
2. Broadcaster catches this and marks itself as `LIMIT_REACHED`
3. All subsequent broadcasts are skipped (no retries)
4. Error logged: `[PUSHER] Rate limit reached, broadcaster disabled for this session`
5. **Restart server to re-enable** after limit reset

### Monitoring Usage
Check your Pusher dashboard for:
- Messages sent today
- Concurrent connections
- Error rates

**Free Tier Limits**:
- 200,000 messages/day
- 100 concurrent connections
- Unlimited channels

---

## Checking Status

### Via API Endpoint
```bash
curl http://localhost:8000/admin/broadcaster-status
```

Response:
```json
{
  "primary_broadcaster": "pusher",
  "primary_available": true,
  "total_broadcasters": 1,
  "available_broadcasters": 1,
  "broadcast_to_all": false,
  "broadcasters": [
    {
      "name": "pusher",
      "type": "pusher",
      "status": "active",
      "available": true,
      "cluster": "ap2",
      "use_tls": true,
      "message_count": 1247,
      "error_count": 0,
      "configured": true
    }
  ]
}
```

### Via Startup Logs
```
[PUSHER] Initialized successfully (cluster: ap2)
[BROADCASTER_MANAGER] Added broadcaster: pusher
[BROADCASTER_MANAGER] Set primary broadcaster: pusher
[BROADCASTER_MANAGER] Initialized with Pusher as primary
[MAIN] Real-time broadcast configured: pusher (available)
```

### In Frontend
Check browser console for connection messages:
```
[PUSHER] Logs connected
[PUSHER] Admin events connected
```

---

## Troubleshooting

### Issue: "pusher library not installed"
**Solution**:
```bash
conda activate clearstar
pip install pusher
```

### Issue: "Missing configuration: PUSHER_APP_ID, PUSHER_KEY, or PUSHER_SECRET"
**Solution**:
- Check `.env` file has all required variables
- Restart server after adding env vars
- Verify no typos in variable names

### Issue: Frontend not receiving messages
**Checklist**:
1. ✅ Check `NEXT_PUBLIC_PUSHER_KEY` is set in `admin-ui/.env.local`
2. ✅ Check cluster matches between backend and frontend
3. ✅ Open browser console, look for connection errors
4. ✅ Verify backend is broadcasting (check backend logs)
5. ✅ Test with Pusher debug console: [https://dashboard.pusher.com/apps/YOUR_APP_ID/debug_console](https://dashboard.pusher.com/)

### Issue: HTTP 402 - Payment Required
**Cause**: Rate limit reached

**Solution**:
1. Wait for limit to reset (daily reset at midnight UTC)
2. Upgrade Pusher plan if needed
3. Restart backend server after limit resets

### Issue: "Subscription error" in frontend
**Common causes**:
- Wrong `PUSHER_KEY` or `PUSHER_CLUSTER`
- Pusher app disabled/deleted
- Network/firewall blocking WebSocket

**Debug**:
```typescript
// In browser console
Pusher.logToConsole = true;
```

---

## Future: Ably Fallback

### Current Architecture
```
Primary: Pusher ✅
Fallback: None (future: Ably)
```

### Planned (V2)
When Pusher hits limits:
1. Pusher broadcaster marks itself as `LIMIT_REACHED`
2. Broadcaster manager automatically falls back to Ably
3. Frontend connects to Ably instead
4. Seamless continuation of service

### Implementation Steps (Future)
1. Add `ably-python` to requirements.txt
2. Create `services/websocket/ably_broadcaster.py`
3. Update broadcaster manager to add Ably as secondary
4. Update frontend to support dual connections
5. Add auto-switching logic

---

## Cost Estimation

### Free Tier (Current)
- **200K messages/day**
- With 100 workflows/day × 20 broadcasts = 2K messages/day
- **100x headroom** on free tier
- **Cost: $0/month**

### Startup Tier ($29/month)
- **1M messages/day**
- Supports up to 50K workflows/day
- 500 concurrent connections
- Good for production use

### Actual Usage Patterns
- 1 log broadcast = 1 message (deliveries are free!)
- 10 admins watching × 1 broadcast = still 1 message
- Very cost-effective for your use case

---

## Migration from Socket.IO

### What Changed
| Before | After |
|--------|-------|
| Self-hosted Socket.IO server | Cloud-hosted Pusher |
| Port 7000 management | No port management |
| SSL certificate handling | Pusher handles TLS |
| Manual scaling | Auto-scaling |
| Connection pooling issues | Handled by Pusher |

### What Stayed the Same
- Message format (log_data, admin events)
- Frontend API (`connectLogs`, `connectAdminEvents`)
- Database log persistence
- Authentication flow

### Removed Files
- `socketio_server.py` (no longer needed)
- `services/websocket/socketio_events.py` (replaced by broadcasters)
- `services/websocket/http_broadcaster.py` (replaced by pusher_broadcaster)

### Legacy Support
Socket.IO still supported as fallback:
- Set `NEXT_PUBLIC_USE_PUSHER=false` in frontend
- Keep Socket.IO server running separately if needed
- Useful for testing/transition period

---

## Testing

### Test Backend Broadcasting
```bash
# Start backend
python main.py

# In another terminal, trigger a workflow
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "thread_id": "test-123",
    "sop": "Test workflow",
    "initial_data": {}
  }'
```

Watch for:
- `[PUSHER] Initialized successfully`
- No error messages in backend logs
- Messages appearing in Pusher debug console

### Test Frontend Connection
1. Open `http://localhost:3000/logs`
2. Open browser console (F12)
3. Look for: `[PUSHER] Logs connected`
4. Trigger workflow from backend
5. Verify logs appear in UI

### Test Admin Events
1. Open `http://localhost:3000/admin/test-123`
2. Trigger workflow state changes
3. Verify real-time updates appear

---

## Best Practices

### 1. Monitor Usage
- Check Pusher dashboard daily
- Set up usage alerts at 80% of free tier
- Plan upgrade before hitting limits

### 2. Error Handling
- Broadcaster fails gracefully
- Logs still persist to PostgreSQL
- Frontend shows historical logs on page load

### 3. Security
- Never expose `PUSHER_SECRET` to frontend
- Use `NEXT_PUBLIC_` prefix only for public keys
- Rotate secrets if compromised

### 4. Performance
- Keep message payloads small
- Use thread_id filtering on frontend if needed
- Consider Pusher presence channels for "who's watching"

### 5. Development
- Use separate Pusher apps for dev/staging/prod
- Enable `Pusher.logToConsole = true` in development
- Test with Pusher event creator in dashboard

---

## Support

### Pusher Resources
- Documentation: [https://pusher.com/docs/channels](https://pusher.com/docs/channels)
- Support: [https://support.pusher.com](https://support.pusher.com)
- Status: [https://status.pusher.com](https://status.pusher.com)

### Internal Resources
- Code: `services/websocket/` directory
- API endpoint: `GET /admin/broadcaster-status`
- Logs: Search for `[PUSHER]` or `[BROADCASTER_MANAGER]`

---

## Quick Reference

### Environment Variables
```bash
# Backend (.env)
PUSHER_APP_ID=123456
PUSHER_KEY=abcdef123456
PUSHER_SECRET=secret123456
PUSHER_CLUSTER=ap2

# Frontend (.env.local)
NEXT_PUBLIC_PUSHER_KEY=abcdef123456
NEXT_PUBLIC_PUSHER_CLUSTER=ap2
NEXT_PUBLIC_USE_PUSHER=true
```

### Import Statements
```python
# Backend
from services.websocket import broadcast_log, broadcast_admin_event

# Usage
await broadcast_log({
    "text": "Hello world",
    "thread_id": "thread-123",
    "level": "INFO",
    "timestamp": datetime.utcnow().isoformat()
})
```

```typescript
// Frontend
import { connectLogs, connectAdminEvents } from '../../lib/api';

// Usage
const connection = connectLogs((line, threadId) => {
    console.log('Log:', line);
});

// Cleanup
connection.disconnect();
```

---

**Setup complete! Your real-time broadcasting is now powered by Pusher.** 🎉
