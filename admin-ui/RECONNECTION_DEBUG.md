# Simple WebSocket Reconnection - Debug Notes

## What Changed

Added simple auto-reconnection to both WebSocket connections:
- `connectAdminEvents()` - for run events
- `connectLogs()` - for log streaming

## How It Works

1. **Connection closes** → Wait 2 seconds → Reconnect automatically
2. **Intentional close** → Set flag to prevent reconnection
3. **Console logs** → See what's happening in browser DevTools

## Testing

Open browser console and watch for these messages:

```
[API] Admin websocket connected      ✅ Initial connection
[API] Admin websocket closed          ❌ Connection dropped
[API] Reconnecting admin in 2 seconds...  ⏱️ Waiting
[API] Attempting reconnection...      🔄 Retrying
[API] Admin websocket connected      ✅ Back online
```

## Why This Might Work

Your theory: The connection gets lost when navigating from start page to thread page.

This simple reconnection will:
- Detect the disconnect
- Wait 2 seconds (let the page settle)
- Reconnect automatically
- Keep trying if it fails

## Monitor in DevTools

1. Open Chrome DevTools (F12)
2. Go to Console tab
3. Start a workflow
4. Navigate to thread page
5. Watch the console messages

If you see reconnection messages, the WebSocket was dropped and is being restored.

## Next Steps

If this works:
- We know it's just a connection stability issue
- Can add visual indicator (green/red dot)
- Can optimize reconnection timing

If it doesn't work:
- Check console for errors
- Try IIS configuration fixes
- Consider switching to SSE

Keep it simple for now - let's see if basic reconnection solves it! 🚀
