# Simple AWS Gateway Setup - Quick Guide

## What You Need to Fill in AWS Console

### 1. API Gateway - Create WebSocket API

**Form Fields:**
```
API name: clearstar-websocket
Route selection expression: $request.body.action
Description: Simple WebSocket for Clearstar
```

### 2. Lambda Function - Create

**Form Fields:**
```
Function name: clearstar-websocket-handler
Runtime: Node.js 20.x
Architecture: x86_64
Handler: handler.handler
```

**Code:**
- Copy entire contents of `lambda-simple/handler.js`
- Paste into Lambda code editor (replace index.js content)
- Click Deploy

**Or upload as ZIP:**
```bash
cd lambda-simple
npm install
zip -r function.zip handler.js node_modules package.json
# Upload function.zip in Lambda console
```

**IAM Policy (add to Lambda role):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["execute-api:ManageConnections"],
      "Resource": "arn:aws:execute-api:*:*:*/*/*/*"
    }
  ]
}
```

### 3. API Gateway Routes - Create 3 Routes

**Route 1:**
```
Route key: $connect
Integration: Lambda
Lambda function: clearstar-websocket-handler
```

**Route 2:**
```
Route key: $disconnect
Integration: Lambda
Lambda function: clearstar-websocket-handler
```

**Route 3:**
```
Route key: $default
Integration: Lambda
Lambda function: clearstar-websocket-handler
```

Grant permissions when prompted.

### 4. Deploy Stage

**Form Fields:**
```
Stage name: production
Auto deploy: ✅ Enabled
```

### 5. Get Your WebSocket URL

After deploying, copy the WebSocket URL shown:
```
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
```

---

## Where Each Code Goes

### AWS Lambda (`handler.js`)
```javascript
// This entire file goes into the Lambda function code editor
// Location: AWS Lambda Console → clearstar-websocket-handler → Code
// Don't forget package.json and run npm install!
```

### Your Backend (`broadcaster.js` or `broadcaster.py`)
```javascript
// Copy broadcaster.js to your Node.js backend
// OR use broadcaster.py for Python backend
// Use it to broadcast messages to connected clients
```

### Frontend (already done)
```typescript
// File: admin-ui/src/lib/awsGateway.ts
// Already created - no changes needed
```

---

## Configuration Values Summary

| What | Where to Set | Value |
|------|-------------|-------|
| API Name | API Gateway Console | `clearstar-websocket` |
| Route Expression | API Gateway Console | `$request.body.action` |
| Lambda Name | Lambda Console | `clearstar-websocket-handler` |
| Lambda Runtime | Lambda Console | Node.js 20.x |
| Lambda Handler | Lambda Console | `handler.handler` |
| Stage Name | API Gateway Stages | `production` |
| Frontend Env Var | `.env.local` | Your WebSocket URL |

---

## Frontend Configuration

Update `admin-ui/.env.local`:

```bash
NEXT_PUBLIC_PUSHER_KEY=wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
NEXT_PUBLIC_PUSHER_CLUSTER=us-east-1
```

Replace `abc123xyz` with your actual API ID.

---

## Backend Configuration

**Node.js Backend:**

```javascript
const { initBroadcaster, registerConnection, broadcastAdminEvent } = require('./broadcaster');

// Initialize once at startup
initBroadcaster({
    apiId: 'abc123xyz',  // Your API ID
    region: 'us-east-1',
    stage: 'production'
});

// Register connections (track when clients connect)
registerConnection('connection-id-from-client');

// Broadcast events
await broadcastAdminEvent({
    type: 'run_started',
    thread_id: 'thread-123',
    run_name: 'My Workflow'
});
```

**Python Backend:**

Use the Python version `broadcaster.py` with the same API (see lambda-simple folder).

---

## Testing

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production

# Send subscribe
> {"action":"subscribe","channel":"admin"}

# Should receive
< {"type":"subscription_succeeded","channel":"admin"}
```

---

## That's It!

Total resources created:
1. ✅ 1 API Gateway WebSocket API
2. ✅ 1 Lambda function
3. ✅ 3 Routes
4. ✅ 1 Stage

**No DynamoDB, No complexity!**
