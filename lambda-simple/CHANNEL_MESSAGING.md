# Channel-Based WebSocket Messaging

Complete guide for the updated channel-based messaging system.

## 🎯 Core Concept

**Everything is channel-based!**
- Clients subscribe to channels
- Anyone sends to a channel → All subscribers receive
- Optional: Send to specific connectionId

---

## 📡 WebSocket Messages (Client Side)

### 1. Subscribe to Channel

```javascript
ws.send(JSON.stringify({
    action: 'subscribe',
    channel: 'admin'
}));

// Response 1:
{
    type: 'connection_id',
    connection_id: 'abc123...'
}

// Response 2:
{
    type: 'subscription_succeeded',
    channel: 'admin'
}
```

### 2. Unsubscribe from Channel

```javascript
ws.send(JSON.stringify({
    action: 'unsubscribe',
    channel: 'admin'
}));

// Response:
{
    type: 'unsubscribe_succeeded',
    channel: 'admin'
}
```

### 3. Send to Channel (Broadcast to All Subscribers)

```javascript
ws.send(JSON.stringify({
    action: 'send',
    channel: 'admin',
    event: 'admin_event',
    data: {
        type: 'run_started',
        thread_id: 'thread-123',
        run_name: 'My Workflow'
    }
}));

// You receive acknowledgment:
{
    type: 'send_success',
    channel: 'admin',
    sent: 5,
    failed: 0
}

// All subscribers receive:
{
    channel: 'admin',
    event: 'admin_event',
    data: {
        type: 'run_started',
        thread_id: 'thread-123',
        run_name: 'My Workflow'
    },
    from: 'xyz789...' // sender's connectionId
}
```

### 4. Send to Specific Connection

```javascript
ws.send(JSON.stringify({
    action: 'send',
    connectionId: 'target-connection-id',
    event: 'private_message',
    data: {
        message: 'Hello specific client!'
    }
}));

// Only that connection receives the message
```

---

## 🔌 HTTP Broadcast (Backend)

Backend can trigger broadcasts via HTTP:

```bash
curl -X POST https://your-api.amazonaws.com/production/broadcast \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "admin",
    "event": "admin_event",
    "data": {
        "type": "run_started",
        "thread_id": "123"
    }
  }'
```

**Python:**
```python
from simple_broadcaster import broadcast_admin_event

broadcast_admin_event({
    'type': 'run_started',
    'thread_id': '123'
})
```

**Node.js:**
```javascript
const { broadcastAdminEvent } = require('./simple_broadcaster');

await broadcastAdminEvent({
    type: 'run_started',
    thread_id: '123'
});
```

---

## 💡 Use Cases

### Use Case 1: Real-Time Log Streaming

**Backend sends logs to "logs" channel:**

```python
# Your REST API maintains one WebSocket connection
ws.send(json.dumps({
    'action': 'send',
    'channel': 'logs',
    'event': 'log',
    'data': {
        'text': 'Step 1 completed',
        'thread_id': 'thread-123',
        'timestamp': '2024-01-20T10:00:00Z'
    }
}))
```

**All clients subscribed to "logs" receive it instantly.**

### Use Case 2: Workflow Status Updates

**Backend broadcasts workflow events:**

```python
ws.send(json.dumps({
    'action': 'send',
    'channel': 'admin',
    'event': 'admin_event',
    'data': {
        'type': 'run_started',
        'thread_id': 'thread-123',
        'run_name': 'Data Pipeline',
        'sop': 'ETL Process'
    }
}))
```

### Use Case 3: Private Messages to Specific Client

**Send approval request to specific connection:**

```python
ws.send(json.dumps({
    'action': 'send',
    'connectionId': 'abc123...',
    'event': 'approval_required',
    'data': {
        'workflow_id': 'workflow-456',
        'step': 'manual_review'
    }
}))
```

---

## 🏗️ Backend WebSocket Connection

Your REST API should maintain ONE persistent WebSocket connection:

### Python Example

```python
import websocket
import json
import threading

class BackendWebSocket:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.connection_id = None
        self.connected = False
        
    def connect(self):
        """Connect and subscribe to channels"""
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Run in background thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
    
    def on_open(self, ws):
        print("Connected to WebSocket")
        # Subscribe to admin channel (optional if backend also wants to receive)
        self.subscribe('admin')
    
    def on_message(self, ws, message):
        data = json.loads(message)
        
        if data.get('type') == 'connection_id':
            self.connection_id = data['connection_id']
            print(f"Got connection ID: {self.connection_id}")
            self.connected = True
        
        elif data.get('type') == 'subscription_succeeded':
            print(f"Subscribed to: {data['channel']}")
    
    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed, reconnecting...")
        self.connected = False
        # Implement reconnection logic here
    
    def subscribe(self, channel):
        """Subscribe to a channel"""
        self.ws.send(json.dumps({
            'action': 'subscribe',
            'channel': channel
        }))
    
    def send_to_channel(self, channel, event, data):
        """Send message to all subscribers of a channel"""
        if not self.connected:
            print("Not connected!")
            return False
        
        self.ws.send(json.dumps({
            'action': 'send',
            'channel': channel,
            'event': event,
            'data': data
        }))
        return True

# Initialize once at app startup
backend_ws = BackendWebSocket('wss://your-api.amazonaws.com/production')
backend_ws.connect()

# Use anywhere in your app
def log_to_clients(message, thread_id):
    backend_ws.send_to_channel('logs', 'log', {
        'text': message,
        'thread_id': thread_id
    })

def notify_run_started(thread_id, run_name):
    backend_ws.send_to_channel('admin', 'admin_event', {
        'type': 'run_started',
        'thread_id': thread_id,
        'run_name': run_name
    })
```

---

## 🔄 Message Flow Examples

### Example 1: Backend Sends Logs

```
Backend (via WebSocket)
    ↓ action: 'send', channel: 'logs'
Lambda
    ↓ Finds all connections subscribed to 'logs'
    ↓ Sends to each via WebSocket
Client 1, Client 2, Client 3 (all receive)
```

### Example 2: HTTP Broadcast

```
Backend (via HTTP POST)
    ↓ POST /broadcast
Lambda
    ↓ Validates access key
    ↓ Finds all connections subscribed to channel
    ↓ Sends to each via WebSocket
Client 1, Client 2, Client 3 (all receive)
```

### Example 3: Client-to-Client via Channel

```
Client 1
    ↓ action: 'send', channel: 'chat'
Lambda
    ↓ Broadcasts to all on 'chat'
    ↓ (including Client 1 unless excluded)
Client 1, Client 2, Client 3 (all receive)
```

---

## 🎯 Best Practices

### 1. Channel Naming

Use hierarchical channel names:
- `admin` - Global admin events
- `logs` - All log messages
- `logs:thread-123` - Logs for specific thread
- `workflow:abc` - Specific workflow updates

### 2. Backend Connection

- **One persistent connection** for your backend
- Reconnect automatically on disconnect
- Use connection pooling if multiple backend instances

### 3. Error Handling

Always handle:
- Connection failures
- Message send failures
- Subscription errors

### 4. Performance

- Don't send too large messages (< 128KB recommended)
- Use channels to filter (don't broadcast everything to everyone)
- Consider connection limits (~10k concurrent for Lambda)

---

## 📊 Summary

| Action | Who | How | What Happens |
|--------|-----|-----|--------------|
| **Subscribe** | Client | WebSocket | Gets added to channel subscriber list |
| **Unsubscribe** | Client | WebSocket | Gets removed from channel |
| **Send to Channel** | Backend/Client | WebSocket | All channel subscribers receive |
| **Send to Connection** | Backend/Client | WebSocket | Specific client receives |
| **Broadcast** | Backend | HTTP | All channel subscribers receive |

**Key Point:** Channels are the core routing mechanism. Everything flows through channels! 🎉
