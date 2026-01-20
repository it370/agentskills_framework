# WebSocket Test Scripts

Simple test scripts to verify your AWS API Gateway WebSocket deployment.

## Quick Test

### 1. Install dependencies

```bash
cd lambda-simple
npm install ws
```

Or if using the test package:
```bash
npm install --save-dev ws
```

### 2. Run basic test

```bash
node test-websocket.js wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
```

Replace with your actual WebSocket URL.

## What the test does

1. ✅ Connects to WebSocket
2. ✅ Subscribes to 'admin' channel
3. ✅ Sends a test message
4. ✅ Receives responses
5. ✅ Closes connection

## Expected Output

```
============================================================
AWS API Gateway WebSocket Test
============================================================
URL: wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production

✅ Connected to WebSocket!
⏳ Sending subscribe message...

📨 Received message:
{
  "type": "subscription_succeeded",
  "channel": "admin"
}

✅ Successfully subscribed to channel: admin
⏳ Sending test message...

📨 Received message:
{
  "type": "message",
  "data": {
    "type": "test",
    "message": "Hello from test script!",
    "timestamp": "2024-01-20T10:30:00.000Z"
  }
}

✅ Test completed successfully!
🔌 Closing connection...

🔌 Connection closed (Code: 1000)

============================================================
Test complete!
============================================================
```

## Full Test (with Broadcasting)

Test both client and server-side broadcasting:

### 1. Edit configuration in test-full.js

```javascript
const WS_URL = 'wss://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/production';
const API_ID = 'YOUR-API-ID';
const REGION = 'us-east-1';
const STAGE = 'production';
```

### 2. Run

```bash
node test-full.js
```

## Troubleshooting

### Error: "Connection refused" or "Connection failed"

**Check:**
- Is the WebSocket URL correct?
- Is API Gateway stage deployed?
- Are routes configured correctly?

**Solution:**
```bash
# Verify URL format
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
     ^^^^^^^^^ Your API ID
                                        ^^^^^^^^^ Your region
                                                              ^^^^^^^^^^ Your stage
```

### Error: "GoneException" or "Connection closed immediately"

**Check:**
- Lambda function is deployed
- Lambda has correct IAM permissions
- Lambda execution role includes `execute-api:ManageConnections`

**Solution:**
Check Lambda CloudWatch logs:
```bash
aws logs tail /aws/lambda/clearstar-websocket-handler --follow
```

### No messages received after subscribing

**Check:**
- Lambda $default route is configured
- Lambda code has no errors
- Check Lambda logs for errors

### Test hangs or times out

**Check:**
- API Gateway timeout settings
- Lambda timeout (should be 10+ seconds)
- Network/firewall blocking WebSocket connections

## Test from Browser Console

You can also test directly in browser:

```javascript
const ws = new WebSocket('wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production');

ws.onopen = () => {
    console.log('Connected!');
    ws.send(JSON.stringify({ action: 'subscribe', channel: 'admin' }));
};

ws.onmessage = (event) => {
    console.log('Received:', JSON.parse(event.data));
};

ws.onerror = (error) => {
    console.error('Error:', error);
};
```

## Next Steps

Once test passes:

1. ✅ Update frontend `.env.local` with WebSocket URL
2. ✅ Copy `broadcaster.js` to your backend
3. ✅ Implement connection tracking
4. ✅ Start broadcasting real events!

## Test Commands Reference

```bash
# Basic test
node test-websocket.js wss://YOUR-URL

# Full test (edit file first)
node test-full.js

# Install test dependencies
npm install ws

# Watch Lambda logs while testing
aws logs tail /aws/lambda/clearstar-websocket-handler --follow

# Check API Gateway
aws apigatewayv2 get-apis

# Check Lambda function
aws lambda get-function --function-name clearstar-websocket-handler
```
