// ============================================================
// AWS Lambda Test Events for WebSocket Handler
// ============================================================

// Test Event 1: $connect (Client Connecting)
// Use this to test connection handling
{
  "requestContext": {
    "routeKey": "$connect",
    "eventType": "CONNECT",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-connect",
    "requestTime": "20/Jan/2024:10:30:00 +0000",
    "requestTimeEpoch": 1705750200000,
    "apiId": "abc123xyz"
  }
}

// ============================================================

// Test Event 2: $disconnect (Client Disconnecting)
// Use this to test disconnection handling
{
  "requestContext": {
    "routeKey": "$disconnect",
    "eventType": "DISCONNECT",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-disconnect",
    "requestTime": "20/Jan/2024:10:35:00 +0000",
    "requestTimeEpoch": 1705750500000,
    "apiId": "abc123xyz",
    "disconnectStatusCode": 1000,
    "disconnectReason": "Client closed connection"
  }
}

// ============================================================

// Test Event 3: $default - Subscribe to Channel
// Use this to test subscription handling
{
  "requestContext": {
    "routeKey": "$default",
    "eventType": "MESSAGE",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-message-1",
    "requestTime": "20/Jan/2024:10:31:00 +0000",
    "requestTimeEpoch": 1705750260000,
    "apiId": "abc123xyz"
  },
  "body": "{\"action\":\"subscribe\",\"channel\":\"admin\"}"
}

// ============================================================

// Test Event 4: $default - Unsubscribe from Channel
// Use this to test unsubscription handling
{
  "requestContext": {
    "routeKey": "$default",
    "eventType": "MESSAGE",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-message-2",
    "requestTime": "20/Jan/2024:10:32:00 +0000",
    "requestTimeEpoch": 1705750320000,
    "apiId": "abc123xyz"
  },
  "body": "{\"action\":\"unsubscribe\",\"channel\":\"admin\"}"
}

// ============================================================

// Test Event 5: $default - Send Message
// Use this to test message handling
{
  "requestContext": {
    "routeKey": "$default",
    "eventType": "MESSAGE",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-message-3",
    "requestTime": "20/Jan/2024:10:33:00 +0000",
    "requestTimeEpoch": 1705750380000,
    "apiId": "abc123xyz"
  },
  "body": "{\"action\":\"message\",\"data\":{\"type\":\"test\",\"message\":\"Hello World\",\"timestamp\":\"2024-01-20T10:33:00.000Z\"}}"
}

// ============================================================

// Test Event 6: $default - Unknown Action (Error Case)
// Use this to test error handling
{
  "requestContext": {
    "routeKey": "$default",
    "eventType": "MESSAGE",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-message-4",
    "requestTime": "20/Jan/2024:10:34:00 +0000",
    "requestTimeEpoch": 1705750440000,
    "apiId": "abc123xyz"
  },
  "body": "{\"action\":\"unknown_action\",\"data\":{}}"
}

// ============================================================

// Test Event 7: $default - Invalid JSON (Error Case)
// Use this to test JSON parsing error handling
{
  "requestContext": {
    "routeKey": "$default",
    "eventType": "MESSAGE",
    "connectionId": "test-connection-123",
    "domainName": "abc123xyz.execute-api.us-east-1.amazonaws.com",
    "stage": "production",
    "requestId": "test-request-message-5",
    "requestTime": "20/Jan/2024:10:34:30 +0000",
    "requestTimeEpoch": 1705750470000,
    "apiId": "abc123xyz"
  },
  "body": "{invalid json here}"
}

// ============================================================
// NOTES:
// ============================================================
// 
// 1. Replace 'abc123xyz' with your actual API Gateway ID
// 2. The 'body' field should be a JSON string (not an object)
// 3. connectionId can be any test value - it won't actually send to a real connection
// 4. When testing sending to connections, it will fail (GoneException) since 
//    test-connection-123 doesn't exist - this is expected
// 5. Check CloudWatch logs to see the output
// 
// ============================================================
