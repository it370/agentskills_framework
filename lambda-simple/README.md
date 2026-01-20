# Simple AWS API Gateway WebSocket Setup

Ultra-simple WebSocket implementation using AWS API Gateway with in-memory connection tracking.

## Architecture

```
Client (Browser) <--WebSocket--> API Gateway <--> Single Lambda <--> Your Backend
                                                      |
                                                   In-Memory
                                                  Connection List
```

**No DynamoDB, No complexity - Just a simple Lambda function!**

---

## Step 1: Create WebSocket API in AWS Console

Go to **API Gateway Console** → **Create API** → **WebSocket API**

### Fill the form:

```
API name: clearstar-websocket
Route selection expression: $request.body.action
Description: Simple WebSocket for Clearstar Skills
```

Click **Create API**

---

## Step 2: Create Single Lambda Function

Go to **Lambda Console** → **Create function**

### Fill the form:

```
Function name: clearstar-websocket-handler
Runtime: Node.js 20.x
Architecture: x86_64
Execution role: Create a new role with basic Lambda permissions
```

Click **Create function**

### Add IAM Permissions

1. Go to **Configuration** → **Permissions**
2. Click on the role name
3. Click **Add permissions** → **Create inline policy**
4. Add this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "execute-api:ManageConnections"
      ],
      "Resource": "arn:aws:execute-api:*:*:*/*/*/*"
    }
  ]
}
```

Name it: `ApiGatewayManageConnections`

### Upload Lambda Code

**Option A: Using Console (Simple)**

1. Copy the code from `handler.js`
2. Paste it into the Lambda code editor (replacing index.js)
3. Rename handler to: `handler.handler`
4. Click **Deploy**

**Option B: Using ZIP Upload (Recommended)**

```bash
cd lambda-simple
npm install
zip -r function.zip handler.js node_modules package.json
```

Then upload `function.zip` in Lambda console under **Code source** → **Upload from** → **.zip file**

Set handler to: `handler.handler`

---

## Step 3: Configure API Gateway Routes

Back in API Gateway Console, select your API.

### Create Routes:

Go to **Routes** → **Create**

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

### Grant Permissions

For each route, AWS will ask to grant API Gateway permission to invoke Lambda. Click **Grant**.

Or run these commands:

```bash
aws lambda add-permission \
  --function-name clearstar-websocket-handler \
  --statement-id apigateway-connect \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com

aws lambda add-permission \
  --function-name clearstar-websocket-handler \
  --statement-id apigateway-disconnect \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com

aws lambda add-permission \
  --function-name clearstar-websocket-handler \
  --statement-id apigateway-default \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com
```

---

## Step 4: Deploy Stage

Go to **Stages** → **Create**

### Fill the form:

```
Stage name: production
Auto deploy: ✅ Enabled
```

Click **Create**

### Get Your WebSocket URL

After creating, you'll see the **WebSocket URL**:

```
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
```

**Copy this URL** - you'll use it in your frontend!

---

## Step 5: Test with wscat

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production

# Subscribe to channel
> {"action":"subscribe","channel":"admin"}

# Should receive:
< {"type":"subscription_succeeded","channel":"admin"}
```

---

## Step 6: Frontend Configuration

Update your `.env.local`:

```bash
NEXT_PUBLIC_PUSHER_KEY=wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
NEXT_PUBLIC_PUSHER_CLUSTER=us-east-1
```

**That's it!** Your existing `awsGateway.ts` client will work.

---

## Step 7: Backend Integration (Broadcasting)

Copy `broadcaster.js` to your Node.js backend and use it:

```javascript
const { initBroadcaster, registerConnection, broadcastAdminEvent } = require('./broadcaster');

// Initialize once at startup
initBroadcaster({
    apiId: 'abc123xyz',  // Your API ID from the WebSocket URL
    region: 'us-east-1',
    stage: 'production'
});

// When client connects (you'll need to implement a way to track this)
// Option 1: Client sends connection_id to your backend after connecting
// Option 2: Use API Gateway HTTP integration to notify your backend

registerConnection('connection-id-here');

// Broadcast to all clients
await broadcastAdminEvent({
    type: 'run_started',
    thread_id: 'abc123',
    run_name: 'My Workflow'
});
```

**For Python Backend:**

If your backend is Python (like `engine.py`), you can use the Python version (`broadcaster.py`) which has the same API.

---

## Important Notes

### Connection Tracking Limitation

**Problem:** API Gateway doesn't provide a way to list all active connections without external storage.

**Solutions:**

**Option 1 (Simple - Current Implementation):**
- Keep connections in memory in your backend
- When client connects, it notifies your backend with its connection_id
- Your backend maintains the list
- **Limitation:** List is lost if backend restarts

**Option 2 (Better - Use Redis):**
```javascript
const redis = require('redis');
const client = redis.createClient({ url: 'redis://your-redis-host:6379' });

async function registerConnection(connectionId) {
    await client.sAdd('ws_connections', connectionId);
}

async function getAllConnections() {
    return await client.sMembers('ws_connections');
}
```

**Option 3 (Production - Use DynamoDB):**
- Store connections in DynamoDB (my previous complex solution)
- Survives restarts
- Scales automatically

**For your simple use case, Option 1 (in-memory) works fine!**

---

## How Client Notifies Backend of Connection

Add this to your frontend after WebSocket connects:

```typescript
// In awsGateway.ts, after connection succeeds
this.ws.onopen = () => {
  const connectionId = this.getConnectionId(); // You'll need to extract this
  
  // Notify your backend
  fetch(`${API_BASE}/websocket/register`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ connection_id: connectionId })
  });
}
```

API Gateway doesn't directly expose connection_id to clients, so you have two options:

**Option A:** Have Lambda send it on connect:
```javascript
// In handler.js, $connect route:
await sendToConnection(apiClient, connectionId, {
    type: 'connection_id',
    connection_id: connectionId
});
```

**Option B:** Backend accepts any client message and tracks who sent it (my recommendation):
```javascript
// In your backend, when receiving any message from client:
// API Gateway provides connection_id in the route context
const connectionId = event.requestContext.connectionId;
registerConnection(connectionId);
```

---

## Complete Configuration Summary

### AWS Console Values:

| Field | Value |
|-------|-------|
| **API Gateway** | |
| API name | `clearstar-websocket` |
| Route expression | `$request.body.action` |
| Stage | `production` |
| **Lambda** | |
| Function name | `clearstar-websocket-handler` |
| Runtime | Python 3.12 |
| Timeout | 10 seconds |
| Memory | 256 MB |
| **Routes** | |
| $connect | clearstar-websocket-handler |
| $disconnect | clearstar-websocket-handler |
| $default | clearstar-websocket-handler |

### Files:

- `handler.py` → Upload to Lambda function
- `broadcaster.py` → Copy to your backend code

### Environment Variables:

**Frontend:**
```bash
NEXT_PUBLIC_PUSHER_KEY=wss://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/production
```

**Backend:**
```python
init_broadcaster(
    api_id='YOUR-API-ID',
    region='us-east-1',
    stage='production'
)
```

---

## Testing Broadcast

```javascript
// Test from Node.js
const { initBroadcaster, registerConnection, broadcastAdminEvent } = require('./broadcaster');

initBroadcaster({
    apiId: 'abc123xyz',
    region: 'us-east-1',
    stage: 'production'
});

// Manually register a connection (get ID from wscat or browser)
registerConnection('XYZ123connectionID');

// Broadcast
const result = await broadcastAdminEvent({
    type: 'test',
    message: 'Hello!'
});

console.log(result);  // { sent: 1, failed: 0, stale: 0 }
```

---

## Cost

- **API Gateway:** $1.00 per million messages
- **Lambda:** $0.20 per million invocations + execution time
- **Total:** ~$2-5/month for typical usage

---

## Troubleshooting

### Connection Fails
- Check Lambda permissions include `execute-api:ManageConnections`
- Verify stage is deployed
- Test Lambda directly in console

### Messages Not Received
- Ensure connection is registered via `register_connection()`
- Check Lambda CloudWatch logs
- Verify WebSocket is connected (wscat test)

### Broadcast Doesn't Work
- Make sure `init_broadcaster()` was called
- Check connection was registered
- Verify API ID is correct

---

## Next Steps

1. Create API Gateway WebSocket API
2. Create Lambda function with `handler.py` code
3. Configure 3 routes ($connect, $disconnect, $default)
4. Deploy stage
5. Get WebSocket URL
6. Test with wscat
7. Add `broadcaster.py` to your backend
8. Update frontend `.env.local`
9. Implement connection registration
10. Start broadcasting!

---

That's it! Much simpler than the complex solution. 🎉
