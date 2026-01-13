# Socket.IO Server Separation

## Overview

The WebSocket functionality has been migrated to a standalone Socket.IO server running on port 7000, separate from the REST API on port 8000.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  CLIENT (Admin UI)                      │
└─────────────────────────────────────────────────────────┘
           │                           │
           │ HTTP (8000)               │ Socket.IO (7000)
           ▼                           ▼
    ┌──────────────┐          ┌──────────────────┐
    │  REST API    │          │  Socket.IO Server│
    │  Port: 8000  │          │  Port: 7000      │
    │              │          │                  │
    │  Endpoints:  │          │  Namespaces:     │
    │  /start      │          │  /logs           │
    │  /status     │          │  /admin          │
    │  /approve    │          │                  │
    │  /admin/*    │          │  Events:         │
    │  /health     │          │  - log           │
    │              │          │  - admin_event   │
    └──────────────┘          └──────────────────┘
            │                         │
            └────────┬────────────────┘
                     │
                     ▼
            ┌─────────────────┐
            │  Pub/Sub (Redis)│
            └─────────────────┘
```

## Running

### Start Both Servers
```bash
python main.py
```

This starts:
- **REST API** on port 8000
- **Socket.IO Server** on port 7000

### Start Individually

**REST API only:**
```bash
uvicorn api:api --host 0.0.0.0 --port 8000
```

**Socket.IO Server only:**
```bash
python socketio_server.py
```

## Configuration

### Environment Variables

```bash
# REST API
REST_API_HOST=0.0.0.0
REST_API_PORT=8000

# Socket.IO Server
SOCKETIO_HOST=0.0.0.0
SOCKETIO_PORT=7000
SOCKETIO_CORS_ORIGINS=*

# Admin UI (frontend)
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_SOCKETIO_BASE=http://localhost:7000
```

## Socket.IO Endpoints

### `/logs` Namespace
**Purpose:** Real-time log streaming

**Event:** `log`
```javascript
{
  "text": "log message",
  "thread_id": "thread-123",
  "level": "INFO",
  "timestamp": "2024-01-01T00:00:00"
}
```

**Client Example:**
```typescript
import { io } from 'socket.io-client';

const socket = io('http://localhost:7000/logs');
socket.on('log', (data) => {
  console.log(data.text);
});
```

### `/admin` Namespace
**Purpose:** Workflow run updates and admin events

**Event:** `admin_event`
```javascript
{
  "type": "run_event",
  "data": {
    "thread_id": "thread-123",
    "checkpoint_id": "...",
    "metadata": {...}
  }
}
```

**Client Example:**
```typescript
import { io } from 'socket.io-client';

const socket = io('http://localhost:7000/admin');
socket.on('admin_event', (data) => {
  console.log('Run event:', data);
});
```

## Monitoring

### Socket.IO Server Health
```bash
GET http://localhost:7000/health
```

Response:
```json
{
  "status": "healthy",
  "service": "socketio",
  "port": 7000,
  "connections": {
    "log_connections": 2,
    "admin_connections": 1,
    "total_connections": 3
  }
}
```

### Connection Statistics
```bash
GET http://localhost:7000/stats
```

## Benefits

1. **Separation of Concerns**: Real-time communication isolated from business logic
2. **Independent Scaling**: Scale Socket.IO server separately based on connection load
3. **Better Resource Management**: Different resource profiles for HTTP vs WebSocket
4. **Easier Debugging**: Clear separation makes troubleshooting simpler
5. **Technology Flexibility**: Can upgrade/replace Socket.IO without touching REST API

## Migration Notes

### What Changed

**Before:**
- WebSocket endpoints on REST API port 8000
- `/ws/logs` and `/ws/admin` endpoints

**After:**
- Socket.IO server on port 7000
- `/logs` and `/admin` namespaces
- Socket.IO protocol (better reconnection, fallback to polling)

### Admin UI Changes

Updated to use Socket.IO client:
```bash
# Install dependency
npm install socket.io-client

# Update environment
NEXT_PUBLIC_SOCKETIO_BASE=http://localhost:7000
```

### Code Changes

**Dependencies:**
```bash
# Python
pip install python-socketio[asyncio_server]

# Admin UI
npm install socket.io-client
```

## Troubleshooting

### Issue: Cannot connect to Socket.IO
**Check:**
1. Socket.IO server is running: `curl http://localhost:7000/health`
2. CORS configured: Check `SOCKETIO_CORS_ORIGINS`
3. Firewall allows port 7000

### Issue: Logs not streaming
**Check:**
1. Socket.IO broadcast configured in `main.py`
2. Client connected to `/logs` namespace
3. Check Socket.IO server logs for errors

### Issue: Admin events not received
**Check:**
1. Pub/sub listener running (check Socket.IO server logs)
2. Client connected to `/admin` namespace
3. Redis/memory pub/sub configured correctly

## Files Changed

### New Files
- `socketio_server.py` - Standalone Socket.IO server
- `services/websocket/socketio_events.py` - Socket.IO event handlers
- `documentations/SOCKETIO_MIGRATION.md` - This file

### Modified Files
- `main.py` - Launches both servers
- `log_stream.py` - Socket.IO broadcast integration
- `admin_events.py` - Socket.IO broadcast integration
- `api/main.py` - Removed WebSocket endpoints
- `admin-ui/package.json` - Added socket.io-client
- `admin-ui/src/lib/api.ts` - Socket.IO client implementation
- `requirements.txt` - Added python-socketio

## Performance

**Connection Overhead:**
- WebSocket: ~1-2KB per connection
- Socket.IO: ~2-3KB per connection (includes protocol overhead)

**Benefits:**
- Auto-reconnection
- Fallback to polling if WebSocket unavailable
- Better mobile/corporate firewall compatibility
- Room/namespace support for future features
