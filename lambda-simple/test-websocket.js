/**
 * Simple WebSocket Test Script
 * 
 * Test your AWS API Gateway WebSocket deployment
 * 
 * Usage:
 *   node test-websocket.js wss://abc123xyz.execute-api.us-east-1.amazonaws.com/production
 */

const WebSocket = require('ws');

// Get WebSocket URL from command line argument
const WS_URL = process.argv[2] || 'wss://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/production';

console.log('='.repeat(60));
console.log('AWS API Gateway WebSocket Test');
console.log('='.repeat(60));
console.log(`URL: ${WS_URL}\n`);

// Create WebSocket connection
const ws = new WebSocket(WS_URL);

// Connection opened
ws.on('open', () => {
    console.log('✅ Connected to WebSocket!');
    console.log('⏳ Sending subscribe message...\n');
    
    // Subscribe to 'admin' channel
    const subscribeMessage = {
        action: 'subscribe',
        channel: 'admin'
    };
    
    ws.send(JSON.stringify(subscribeMessage));
});

// Message received
ws.on('message', (data) => {
    const message = JSON.parse(data.toString());
    
    console.log('📨 Received message:');
    console.log(JSON.stringify(message, null, 2));
    console.log('');
    
    // If subscription succeeded, send a test message
    if (message.type === 'subscription_succeeded') {
        console.log('✅ Successfully subscribed to channel:', message.channel);
        console.log('⏳ Sending test message...\n');
        
        const testMessage = {
            action: 'message',
            data: {
                type: 'test',
                message: 'Hello from test script!',
                timestamp: new Date().toISOString()
            }
        };
        
        ws.send(JSON.stringify(testMessage));
        
        // Close connection after a short delay
        setTimeout(() => {
            console.log('✅ Test completed successfully!');
            console.log('🔌 Closing connection...\n');
            ws.close();
        }, 2000);
    }
});

// Connection closed
ws.on('close', (code, reason) => {
    console.log(`🔌 Connection closed (Code: ${code})`);
    if (reason) {
        console.log(`   Reason: ${reason.toString()}`);
    }
    console.log('\n' + '='.repeat(60));
    console.log('Test complete!');
    console.log('='.repeat(60));
});

// Error handling
ws.on('error', (error) => {
    console.error('❌ WebSocket error:', error.message);
    console.error('\nCommon issues:');
    console.error('  - Check if the WebSocket URL is correct');
    console.error('  - Verify API Gateway stage is deployed');
    console.error('  - Check Lambda permissions');
    console.error('  - Review Lambda CloudWatch logs');
    process.exit(1);
});

// Handle script termination
process.on('SIGINT', () => {
    console.log('\n\n⚠️  Test interrupted by user');
    ws.close();
    process.exit(0);
});
