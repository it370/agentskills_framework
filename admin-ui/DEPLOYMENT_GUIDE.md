# Deployment Solutions for Reverse Proxy Environments

## Problem Statement

When deploying behind IIS or other reverse proxies, WebSocket connections fail because:
- The UI is accessed via `https://domain.com` (proxied to `localhost:3000`)
- WebSocket tries to connect to `wss://domain.com:8000` (port 8000 not exposed)
- Result: WebSocket connection fails

## Solutions Overview

| Solution | Complexity | Pros | Cons | Best For |
|----------|-----------|------|------|----------|
| **IIS WebSocket Proxy** | Low | Simple, native WS support | Requires IIS config | IIS deployments |
| **Server-Sent Events (SSE)** | Low | Works with standard HTTP | One-way only | Read-only updates |
| **Next.js Redis Bridge** | Medium | Everything on port 3000 | Adds Redis dependency | Complex deployments |
| **HTTP Polling** | Low | Works everywhere | Higher latency, more load | Fallback option |

---

## Solution 1: IIS WebSocket Proxy (Recommended for IIS) ⭐

### Architecture
```
Browser → https://domain.com/api/* → IIS → http://localhost:8000/*
Browser → wss://domain.com/ws/* → IIS → ws://localhost:8000/ws/*
Browser → https://domain.com/* → IIS → http://localhost:3000/*
```

### Step 1: Install IIS Requirements

```powershell
# Install WebSocket Protocol
Install-WindowsFeature Web-WebSockets

# Install URL Rewrite Module
# Download from: https://www.iis.net/downloads/microsoft/url-rewrite

# Install Application Request Routing (ARR)
# Download from: https://www.iis.net/downloads/microsoft/application-request-routing
```

### Step 2: Configure IIS URL Rewrite

Edit `web.config` in your IIS site root:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <!-- Proxy API requests to Python backend -->
        <rule name="Proxy API" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="http://localhost:8000/{R:1}" />
        </rule>
        
        <!-- Proxy WebSocket requests to Python backend -->
        <rule name="Proxy WebSocket" stopProcessing="true">
          <match url="^ws/(.*)" />
          <conditions>
            <add input="{HTTP:Upgrade}" pattern="websocket" ignoreCase="true" />
            <add input="{HTTP:Connection}" pattern="Upgrade" ignoreCase="true" />
          </conditions>
          <action type="Rewrite" url="http://localhost:8000/ws/{R:1}" />
          <serverVariables>
            <set name="HTTP_SEC_WEBSOCKET_EXTENSIONS" value="" />
          </serverVariables>
        </rule>
        
        <!-- Proxy everything else to Next.js -->
        <rule name="Proxy Next.js" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://localhost:3000/{R:1}" />
        </rule>
      </rules>
    </rewrite>
    
    <!-- Enable WebSocket support -->
    <webSocket enabled="true" />
  </system.webServer>
</configuration>
```

### Step 3: Update Admin UI Configuration

**.env:**
```env
# Don't specify ports - use paths through reverse proxy
NEXT_PUBLIC_API_HOST=https://yourdomain.com/api
NEXT_PUBLIC_WS_HOST=wss://yourdomain.com
```

### Step 4: Test

```powershell
# Test API access
curl https://yourdomain.com/api/admin/runs

# Test WebSocket (using wscat)
npm install -g wscat
wscat -c wss://yourdomain.com/ws/logs
```

---

## Solution 2: Server-Sent Events (SSE)

### When to Use
- One-way updates (server → client) are sufficient
- Simpler than WebSockets
- Works with standard HTTP proxying

### Architecture
```
Browser → https://domain.com/sse/admin → IIS → http://localhost:8000/sse/admin
```

### Step 1: Update Python Backend

Add SSE endpoints to your FastAPI app:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()

async def admin_event_generator():
    """Generate SSE events for admin updates"""
    while True:
        # Get events from your event system
        event = await get_next_admin_event()  # Your implementation
        
        # Format as SSE
        yield f"data: {json.dumps(event)}\n\n"
        
        # Send keepalive every 30s
        await asyncio.sleep(1)

@app.get("/sse/admin")
async def sse_admin():
    return StreamingResponse(
        admin_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.get("/sse/logs")
async def sse_logs():
    return StreamingResponse(
        log_event_generator(),
        media_type="text/event-stream",
    )
```

### Step 2: Update Admin UI

Use the SSE client from `src/lib/realtime.ts`:

```typescript
import { connectAdminEventsSSE, connectLogsSSE } from '@/lib/realtime';

// Replace WebSocket connections
const eventSource = connectAdminEventsSSE((event) => {
  console.log('Event:', event);
});

// Cleanup
return () => eventSource.close();
```

### Step 3: Configure IIS

```xml
<rule name="Proxy SSE" stopProcessing="true">
  <match url="^sse/(.*)" />
  <action type="Rewrite" url="http://localhost:8000/sse/{R:1}" />
</rule>
```

---

## Solution 3: Next.js Redis Bridge

### When to Use
- Everything needs to be on port 3000
- You already have Redis infrastructure
- Want to avoid exposing Python backend

### Architecture
```
Python Backend → Redis Pub/Sub ← Next.js API Route ← Browser
```

### Step 1: Install Dependencies

```bash
cd admin-ui
npm install ioredis
```

### Step 2: Update Python Backend

```python
import redis
import json

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379)

# Publish events
def publish_admin_event(event_data):
    redis_client.publish('admin_events', json.dumps(event_data))

def publish_log(log_data):
    redis_client.publish('log_events', json.dumps(log_data))
```

### Step 3: Create Next.js API Routes

Already created at `admin-ui/src/app/api/events/admin/route.ts`

Create similar for logs:

```typescript
// admin-ui/src/app/api/events/logs/route.ts
import { NextRequest } from 'next/server';
import Redis from 'ioredis';

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();
  
  const stream = new ReadableStream({
    async start(controller) {
      const redis = new Redis({
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379'),
      });

      redis.subscribe('log_events');

      redis.on('message', (channel, message) => {
        const sseMessage = `data: ${message}\n\n`;
        controller.enqueue(encoder.encode(sseMessage));
      });

      request.signal.addEventListener('abort', () => {
        redis.disconnect();
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

### Step 4: Update UI to Use Next.js API Routes

```typescript
// Connect to Next.js API routes instead of Python backend
const eventSource = new EventSource('/api/events/admin');
eventSource.onmessage = (evt) => {
  const data = JSON.parse(evt.data);
  console.log('Event:', data);
};
```

### Step 5: Configure Environment

```env
# .env.local
REDIS_HOST=localhost
REDIS_PORT=6379

# Client-side (no backend port needed)
NEXT_PUBLIC_API_HOST=https://yourdomain.com/api
```

---

## Solution 4: HTTP Polling (Fallback)

### When to Use
- All realtime options fail
- Simple fallback mechanism

### Implementation

Already included in `src/lib/realtime.ts` as `PollingConnection`

### Python Backend

```python
from fastapi import FastAPI, Query
from typing import Optional

# Store events with IDs
event_store = []
event_counter = 0

@app.get("/poll/admin")
async def poll_admin(since: Optional[str] = None):
    """Return events since given ID"""
    since_id = int(since) if since else 0
    recent_events = [e for e in event_store if e['id'] > since_id]
    return recent_events

@app.get("/poll/logs")
async def poll_logs(since: Optional[str] = None):
    since_id = int(since) if since else 0
    recent_logs = [log for log in log_store if log['id'] > since_id]
    return recent_logs
```

### Usage

```typescript
import { PollingConnection } from '@/lib/realtime';

const poller = new PollingConnection(
  '/api/poll/admin',
  (event) => console.log('Event:', event),
  2000  // Poll every 2 seconds
);

poller.start();

// Cleanup
return () => poller.stop();
```

---

## Recommended Approach by Environment

### IIS on Windows Server
1. **Use IIS WebSocket Proxy** (Solution 1)
2. Fallback to SSE if WebSocket issues persist

### Docker/Kubernetes
1. **Use SSE** (Solution 2)
2. Or configure ingress to proxy WebSocket

### Vercel/Netlify
1. **Use Next.js Redis Bridge** (Solution 3)
2. Deploy Python backend separately

### Simple Deployments
1. Start with **HTTP Polling** (Solution 4)
2. Upgrade to SSE when needed

---

## Testing Your Configuration

```javascript
// Test in browser console
const testWebSocket = () => {
  const ws = new WebSocket('wss://yourdomain.com/ws/logs');
  ws.onopen = () => console.log('✅ WebSocket connected');
  ws.onerror = (err) => console.error('❌ WebSocket failed:', err);
};

const testSSE = () => {
  const es = new EventSource('https://yourdomain.com/sse/admin');
  es.onopen = () => console.log('✅ SSE connected');
  es.onerror = (err) => console.error('❌ SSE failed:', err);
};

testWebSocket();
testSSE();
```

---

## Performance Comparison

| Method | Latency | Server Load | Client Load | Bandwidth |
|--------|---------|-------------|-------------|-----------|
| WebSocket | ~5ms | Low | Low | Lowest |
| SSE | ~10ms | Low | Low | Low |
| Redis Bridge | ~15ms | Medium | Low | Low |
| HTTP Polling (2s) | ~1s | High | Medium | Highest |

---

## Troubleshooting

### WebSocket fails with 400/404
- Check IIS WebSocket module is installed
- Verify URL Rewrite rules are correct
- Check if ARR is enabled

### SSE disconnects frequently
- Increase timeout in IIS
- Add keepalive messages every 30s
- Check reverse proxy buffering settings

### High Redis CPU usage
- Reduce publishing frequency
- Use Redis Streams instead of Pub/Sub
- Implement message batching

---

## Next Steps

Choose your solution and I can help implement it fully!
