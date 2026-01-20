# Centralized Broadcasting Architecture

**Simple, clean, secure - all broadcasting logic in AWS Lambda!**

## 🎯 Architecture

```
┌──────────────────┐
│  Your Backend    │
│  (engine.py)     │
│                  │
│  No AWS SDK!     │
│  Just HTTP POST  │
└────────┬─────────┘
         │ HTTP POST + Access Key
         ↓
┌──────────────────────────────────┐
│   API Gateway HTTP Endpoint      │
│   /broadcast                     │
└────────┬─────────────────────────┘
         │ Validates access key
         ↓
┌──────────────────────────────────┐
│   Lambda Function                │
│   - Tracks connections           │
│   - Broadcasts to all clients    │
└────────┬─────────────────────────┘
         │ API Gateway Management API
         ↓
┌──────────────────────────────────┐
│   WebSocket Clients              │
│   (Just receive messages)        │
└──────────────────────────────────┘
```

## ✅ Benefits

- ✅ **Backend**: Just calls HTTP endpoint (no AWS SDK!)
- ✅ **Centralized**: All logic in Lambda
- ✅ **Secure**: Access key authentication
- ✅ **Simple**: Minimal backend code
- ✅ **No Credentials**: Backend doesn't need AWS credentials

---

## 🚀 Setup

### 1. Update Lambda Function

Replace `handler.js` with `handler-centralized.js`:

```bash
cd lambda-simple
cp handler-centralized.js handler.js
```

### 2. Add Environment Variables to Lambda

In AWS Lambda Console → Configuration → Environment variables:

```
BROADCAST_ACCESS_KEY=your-secret-key-here-change-this-to-something-secure
WEBSOCKET_API_ID=abc123xyz
WEBSOCKET_STAGE=production
AWS_REGION=us-east-1
```

### 3. Create HTTP API Gateway Route

**Option A: Add to existing WebSocket API (easier)**

In API Gateway Console → Your WebSocket API → Routes:

Add route:
```
Route key: broadcast
Route type: Non-WebSocket route (HTTP POST)
Integration: Lambda (same function)
```

**Option B: Create separate HTTP API**

Create new HTTP API:
```
API name: clearstar-broadcast-api
Integration: Lambda (clearstar-websocket-handler)
Route: POST /broadcast
Stage: production
```

### 4. Get Broadcast URL

After creating the route, you'll get a URL like:
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/production/broadcast
```

---

## 📝 Backend Configuration

### Python Backend

**1. Install requests:**
```bash
pip install requests
```

**2. Set environment variables:**
```bash
# .env or environment
BROADCAST_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com/production/broadcast
BROADCAST_ACCESS_KEY=your-secret-key-here
```

**3. Use in your code:**
```python
from simple_broadcaster import broadcast_admin_event

# That's it! No AWS SDK needed
broadcast_admin_event({
    'type': 'run_started',
    'thread_id': 'thread-123',
    'run_name': 'My Workflow'
})
```

### Node.js Backend

**1. Set environment variables:**
```bash
export BROADCAST_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com/production/broadcast
export BROADCAST_ACCESS_KEY=your-secret-key-here
```

**2. Use in your code:**
```javascript
const { broadcastAdminEvent } = require('./simple_broadcaster');

// That's it! No AWS SDK needed
await broadcastAdminEvent({
    type: 'run_started',
    thread_id: 'thread-123',
    run_name: 'My Workflow'
});
```

---

## 🧪 Testing

```bash
# Test with curl
curl -X POST https://abc123xyz.execute-api.us-east-1.amazonaws.com/production/broadcast \
  -H "Authorization: Bearer your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "admin",
    "event": "admin_event",
    "data": {
      "type": "test",
      "message": "Hello!"
    }
  }'

# Expected response:
# {"success":true,"channel":"admin","event":"admin_event","sent":2,"failed":0}
```

---

## 🔐 Security

### Access Key Best Practices

1. **Generate a strong key:**
```bash
# Generate random key
openssl rand -base64 32
# Or
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

2. **Store securely:**
   - Use environment variables
   - Never commit to git
   - Different keys for dev/production

3. **Rotate regularly:**
   - Change access key every 90 days
   - Update in both Lambda and backend

---

## 📊 API Reference

### Broadcast Endpoint

**URL:** `POST /broadcast`

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "channel": "admin",
  "event": "admin_event",
  "data": {
    "type": "run_started",
    "thread_id": "123"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "channel": "admin",
  "event": "admin_event",
  "sent": 5,
  "failed": 0
}
```

**Response (Error):**
```json
{
  "error": "Unauthorized"
}
```

---

## 🔄 Migration from Old Broadcaster

### Before (with AWS SDK):
```python
from broadcaster import init_broadcaster, broadcast_admin_event

init_broadcaster('abc123', 'us-east-1', 'production')
broadcast_admin_event({'type': 'test'})
```

### After (simple HTTP):
```python
from simple_broadcaster import broadcast_admin_event

# Just works! No init needed!
broadcast_admin_event({'type': 'test'})
```

---

## 💰 Cost

Same as before! Maybe even cheaper:
- No separate broadcaster infrastructure
- Reuses existing Lambda
- Just one HTTP call per broadcast

---

## ✨ Summary

| Feature | Old Way | New Way |
|---------|---------|---------|
| **Backend needs AWS SDK** | ✅ Yes | ❌ No! |
| **AWS credentials needed** | ✅ Yes | ❌ No! |
| **Separate broadcaster** | ✅ Yes | ❌ No! |
| **Connection tracking** | Backend | Lambda |
| **Authentication** | IAM | Access Key |
| **Complexity** | High | Low |

Your backend is now **super simple** - just HTTP calls! 🎉
