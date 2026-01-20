# Deploy Lambda Function (Node.js)

## Quick Deploy Steps

### Method 1: Console Upload (Easiest)

1. **Prepare the ZIP file:**

```bash
cd lambda-simple
npm install
zip -r function.zip handler.js package.json node_modules/
```

2. **Upload to Lambda:**
   - Go to AWS Lambda Console
   - Select your function: `clearstar-websocket-handler`
   - **Code source** → **Upload from** → **.zip file**
   - Upload `function.zip`
   - Set **Runtime settings** → **Handler**: `handler.handler`
   - Click **Deploy**

3. **Test:**
   - Go to **Test** tab
   - Create test event with WebSocket connect template
   - Click **Test**

---

### Method 2: AWS CLI (Faster Updates)

```bash
cd lambda-simple
npm install
zip -r function.zip handler.js package.json node_modules/

aws lambda update-function-code \
  --function-name clearstar-websocket-handler \
  --zip-file fileb://function.zip
```

---

### Method 3: Direct Code Paste (Quick Test)

1. Copy contents of `handler.js`
2. Paste into Lambda code editor
3. Click **Deploy**

**Note:** This won't include `node_modules`. You'll need to either:
- Add layers for AWS SDK (it's included by default in Node.js runtime)
- Or use ZIP upload method

---

## Dependencies

The handler uses AWS SDK v3 which needs to be included:

**package.json:**
```json
{
  "dependencies": {
    "@aws-sdk/client-apigatewaymanagementapi": "^3.600.0"
  }
}
```

**For Node.js 20.x runtime on Lambda:**
- AWS SDK v3 is NOT included by default
- You MUST include it in your deployment package
- Use ZIP upload method (Method 1 or 2)

---

## Deployment Checklist

Before deploying:

- [ ] `handler.js` file is ready
- [ ] `package.json` is present
- [ ] Run `npm install` to get dependencies
- [ ] Create ZIP with `handler.js`, `package.json`, and `node_modules/`
- [ ] Upload ZIP to Lambda
- [ ] Set handler to `handler.handler`
- [ ] Set runtime to Node.js 20.x
- [ ] IAM role has `execute-api:ManageConnections` permission
- [ ] Test the function

---

## File Structure in ZIP

```
function.zip
├── handler.js
├── package.json
└── node_modules/
    └── @aws-sdk/
        └── client-apigatewaymanagementapi/
            └── ...
```

---

## Testing Locally (Optional)

You can test the handler logic locally:

```javascript
// test.js
const handler = require('./handler');

const mockEvent = {
    requestContext: {
        routeKey: '$connect',
        connectionId: 'test123',
        domainName: 'abc123.execute-api.us-east-1.amazonaws.com',
        stage: 'production'
    }
};

handler.handler(mockEvent, {})
    .then(response => console.log('Response:', response))
    .catch(error => console.error('Error:', error));
```

Run: `node test.js`

---

## Update Lambda Configuration

After deploying code, configure:

### Runtime Settings
```
Runtime: Node.js 20.x
Handler: handler.handler
Architecture: x86_64 (or arm64 for cost savings)
```

### General Configuration
```
Timeout: 10 seconds
Memory: 256 MB
```

### Environment Variables (Optional)
```
LOG_LEVEL=info
```

---

## Common Issues

### Issue: "Cannot find module '@aws-sdk/client-apigatewaymanagementapi'"

**Solution:** Include node_modules in ZIP:
```bash
npm install
zip -r function.zip handler.js package.json node_modules/
```

### Issue: "Handler 'handler.handler' not found"

**Solution:** Check handler configuration:
- File is named `handler.js`
- Export is `exports.handler = async (event, context) => {...}`
- Handler setting is `handler.handler` (file.function)

### Issue: "Permission denied to post to connection"

**Solution:** Add IAM policy to Lambda role:
```json
{
  "Effect": "Allow",
  "Action": ["execute-api:ManageConnections"],
  "Resource": "arn:aws:execute-api:*:*:*/*/*/*"
}
```

---

## Size Optimization (Optional)

To reduce ZIP size:

```bash
# Install only production dependencies
npm install --production

# Exclude unnecessary files
zip -r function.zip handler.js package.json node_modules/ \
  -x "*.md" -x "*.txt" -x "*test*"
```

Expected size: ~200KB - 500KB

---

## Next Steps After Deploy

1. ✅ Deploy Lambda function
2. Configure API Gateway routes to point to this function
3. Deploy API Gateway stage
4. Test with wscat
5. Integrate broadcaster in your backend
6. Monitor CloudWatch logs

---

## Quick Commands Reference

```bash
# Install dependencies
npm install

# Create deployment package
zip -r function.zip handler.js package.json node_modules/

# Deploy via AWS CLI
aws lambda update-function-code \
  --function-name clearstar-websocket-handler \
  --zip-file fileb://function.zip

# Check function configuration
aws lambda get-function-configuration \
  --function-name clearstar-websocket-handler

# View recent logs
aws logs tail /aws/lambda/clearstar-websocket-handler --follow
```
