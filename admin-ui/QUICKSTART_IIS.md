# Quick Configuration for IIS Deployment

## Problem You're Facing

Your setup:
- Python API: `http://localhost:8000`
- Next.js UI: `http://localhost:3000`
- IIS proxies: `https://domain.com` → `localhost:3000`
- Issue: WebSocket tries `wss://domain.com:8000` (not accessible)

## Quickest Solution: Update Your .env

Change your `admin-ui/.env` to:

```env
# Port configuration - leave empty or don't set
NEXT_PUBLIC_API_PORT=
NEXT_PUBLIC_WS_PORT=

# Host configuration - use full paths through your domain
NEXT_PUBLIC_API_HOST=https://yourdomain.com/api
NEXT_PUBLIC_WS_HOST=wss://yourdomain.com
```

## Add to IIS web.config

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <!-- API Proxy -->
        <rule name="API" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="http://localhost:8000/{R:1}" />
        </rule>
        
        <!-- WebSocket Proxy -->
        <rule name="WebSocket" stopProcessing="true">
          <match url="^ws/(.*)" />
          <conditions>
            <add input="{HTTP:Upgrade}" pattern="websocket" ignoreCase="true" />
          </conditions>
          <action type="Rewrite" url="http://localhost:8000/ws/{R:1}" />
        </rule>
        
        <!-- Next.js UI -->
        <rule name="NextJS" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://localhost:3000/{R:1}" />
        </rule>
      </rules>
    </rewrite>
    
    <webSocket enabled="true" />
  </system.webServer>
</configuration>
```

## Alternative: Use SSE Instead of WebSocket

If WebSocket proxying doesn't work, use Server-Sent Events (simpler, more reliable):

### 1. Update your Admin UI

In any file that uses WebSocket, import the SSE version:

```typescript
// Instead of:
// import { connectAdminEvents } from '@/lib/api';

// Use:
import { connectAdminEventsSSE } from '@/lib/realtime';

// Replace WebSocket connection with SSE:
const connection = connectAdminEventsSSE((event) => {
  // Handle event
});

// Cleanup
return () => connection.close();
```

### 2. That's it!

SSE works over regular HTTP, so it'll go through your IIS proxy without any special configuration.

## Even Simpler: HTTP Polling

If both fail, use polling (least efficient but works everywhere):

```typescript
import { PollingConnection } from '@/lib/realtime';

const poller = new PollingConnection(
  'https://yourdomain.com/api/poll/admin',
  (event) => handleEvent(event),
  3000  // Poll every 3 seconds
);

poller.start();
```

## Test Your Setup

Open browser console and run:

```javascript
// Test WebSocket
new WebSocket('wss://yourdomain.com/ws/logs')
  .onopen = () => console.log('✅ WS works');

// Test SSE
new EventSource('https://yourdomain.com/sse/admin')
  .onopen = () => console.log('✅ SSE works');
```

## Which Should You Choose?

**Start with this order:**

1. **IIS WebSocket Proxy** - Try this first (update .env + web.config)
2. **SSE** - If WebSocket doesn't work (requires Python backend changes)
3. **HTTP Polling** - Last resort (simplest, works everywhere)

Need help implementing any of these? Let me know which approach you want to try!
