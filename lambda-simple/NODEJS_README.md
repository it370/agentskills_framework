# AWS Gateway WebSocket - Node.js Implementation

Complete simple WebSocket setup using AWS API Gateway with Node.js Lambda.

## 📦 What's Included

### Lambda Function (Node.js)
- **`handler.js`** - Single Lambda that handles all WebSocket events
- **`package.json`** - Dependencies (AWS SDK v3)
- **`DEPLOY.md`** - Deployment instructions

### Backend Broadcaster
- **`broadcaster.js`** - Node.js version for broadcasting to clients
- **`broadcaster.py`** - Python version (if your backend is Python)

### Documentation
- **`README.md`** - Complete setup guide
- **`DEPLOY.md`** - Lambda deployment guide
- **`../SIMPLE_SETUP.md`** - Quick reference

---

## 🚀 Quick Start

### 1. Create Lambda Function

**AWS Console:**
```
Function name: clearstar-websocket-handler
Runtime: Node.js 20.x
Handler: handler.handler
```

### 2. Deploy Code

```bash
cd lambda-simple
npm install
zip -r function.zip handler.js package.json node_modules/
```

Upload `function.zip` to Lambda console.

### 3. Add IAM Permission

Add this policy to Lambda execution role:
```json
{
  "Effect": "Allow",
  "Action": ["execute-api:ManageConnections"],
  "Resource": "arn:aws:execute-api:*:*:*/*/*/*"
}
```

### 4. Create API Gateway

```
API name: clearstar-websocket
Route expression: $request.body.action
Stage: production

Routes (all use same Lambda):
  - $connect
  - $disconnect
  - $default
```

### 5. Get WebSocket URL

Copy from API Gateway stage:
```
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
```

### 6. Configure Frontend

Update `.env.local`:
```bash
NEXT_PUBLIC_PUSHER_KEY=wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
```

### 7. Use Broadcaster in Backend

**Node.js:**
```javascript
const { initBroadcaster, broadcastAdminEvent } = require('./broadcaster');

initBroadcaster({
    apiId: 'abc123xyz',
    region: 'us-east-1',
    stage: 'production'
});

await broadcastAdminEvent({
    type: 'run_started',
    thread_id: '123'
});
```

**Python:**
```python
from broadcaster import init_broadcaster, broadcast_admin_event

init_broadcaster('abc123xyz', 'us-east-1', 'production')
broadcast_admin_event({'type': 'run_started', 'thread_id': '123'})
```

---

## 📁 Files

| File | Purpose | Goes Where |
|------|---------|-----------|
| `handler.js` | WebSocket Lambda handler | AWS Lambda |
| `package.json` | Lambda dependencies | AWS Lambda (in ZIP) |
| `broadcaster.js` | Node.js broadcaster | Your backend |
| `broadcaster.py` | Python broadcaster | Your backend |
| `DEPLOY.md` | Deployment guide | Reference |
| `README.md` | Complete guide | Reference |

---

## 🔧 Architecture

```
Frontend (Browser)
      ↓ WebSocket (wss://)
API Gateway
      ↓ Routes: $connect, $disconnect, $default
Lambda (handler.js)
      ↑ Sends messages via API Gateway Management API
Your Backend (broadcaster.js)
      ↑ In-memory connection tracking
```

---

## ⚡ Key Features

✅ **Single Lambda** - One function handles everything  
✅ **No Database** - In-memory connection tracking  
✅ **Node.js** - Friendly syntax, easy to debug  
✅ **AWS SDK v3** - Latest AWS SDK  
✅ **Simple** - ~130 lines of code total  

---

## 📝 AWS Configuration Summary

| Setting | Value |
|---------|-------|
| **Lambda** | |
| Name | `clearstar-websocket-handler` |
| Runtime | Node.js 20.x |
| Handler | `handler.handler` |
| Timeout | 10 seconds |
| Memory | 256 MB |
| **API Gateway** | |
| Name | `clearstar-websocket` |
| Type | WebSocket API |
| Routes | `$connect`, `$disconnect`, `$default` |
| Stage | `production` |
| **IAM Policy** | |
| Action | `execute-api:ManageConnections` |
| Resource | `arn:aws:execute-api:*:*:*/*/*/*` |

---

## 🧪 Testing

```bash
# Connect with wscat
wscat -c wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production

# Subscribe to channel
> {"action":"subscribe","channel":"admin"}

# Receive confirmation
< {"type":"subscription_succeeded","channel":"admin"}
```

**Test broadcasting:**
```javascript
const { initBroadcaster, registerConnection, broadcastAdminEvent } = require('./broadcaster');

initBroadcaster({ apiId: 'abc123xyz', region: 'us-east-1', stage: 'production' });
registerConnection('connection-id-from-wscat');

await broadcastAdminEvent({ type: 'test', message: 'Hello!' });
// Check wscat - you should receive the message
```

---

## 💰 Cost

| Service | Cost |
|---------|------|
| API Gateway | $1.00/million messages |
| Lambda | $0.20/million invocations |
| **Total** | ~$2-5/month for typical usage |

---

## 🐛 Troubleshooting

### Lambda errors "Cannot find module"
**Solution:** Include node_modules in ZIP:
```bash
npm install
zip -r function.zip handler.js package.json node_modules/
```

### Messages not sending
**Solution:** Check IAM permission includes `execute-api:ManageConnections`

### Connection not registered
**Solution:** Implement connection tracking - client sends ID to backend after connecting

---

## 📚 Documentation

- **Quick Start**: `../SIMPLE_SETUP.md`
- **Complete Guide**: `README.md`
- **Deployment**: `DEPLOY.md`
- **AWS Console Config**: All values in `../SIMPLE_SETUP.md`

---

## 🎯 Next Steps

1. ✅ Read `DEPLOY.md` for deployment instructions
2. ✅ Deploy Lambda function with `handler.js`
3. ✅ Create API Gateway WebSocket API
4. ✅ Configure routes to point to Lambda
5. ✅ Deploy stage and get WebSocket URL
6. ✅ Test with wscat
7. ✅ Copy `broadcaster.js` to your backend
8. ✅ Implement connection registration
9. ✅ Start broadcasting events!

---

## 💡 Tips

**Development:**
- Use CloudWatch Logs to debug Lambda
- Test Lambda directly in console with test events
- Use wscat to test WebSocket connection

**Production:**
- Consider Redis for connection persistence
- Monitor CloudWatch metrics
- Set up alarms for errors
- Use ARM64 architecture for 20% cost savings

**Connection Tracking:**
- Simple: In-memory (current implementation)
- Better: Redis for persistence
- Best: DynamoDB for full scalability

---

## 🆘 Need Help?

Check these in order:
1. Lambda CloudWatch logs
2. API Gateway execution logs
3. Test with wscat to isolate issues
4. Verify IAM permissions
5. Check handler setting is `handler.handler`

---

## ✨ That's It!

You now have a simple, working WebSocket implementation with AWS Gateway and Node.js Lambda. No database complexity, just clean code that works! 🎉
