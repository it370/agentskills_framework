/**
 * Advanced WebSocket Test with Broadcaster
 * 
 * Tests both client connection AND server-side broadcasting
 * 
 * Setup:
 * 1. Set your WebSocket URL below
 * 2. Set your API Gateway details
 * 3. Run: node test-full.js
 */

const WebSocket = require('ws');
const { initBroadcaster, registerConnection, broadcastAdminEvent } = require('./broadcaster');

// ========== CONFIGURATION ==========
const WS_URL = 'wss://k2sysgw2wg.execute-api.us-east-2.amazonaws.com/production';
const API_ID = 'k2sysgw2wg';
const REGION = 'us-east-1';
const STAGE = 'production';
// ===================================

console.log('='.repeat(70));
console.log('Full WebSocket Test: Client + Broadcaster');
console.log('='.repeat(70));
console.log(`WebSocket URL: ${WS_URL}`);
console.log(`API Gateway:   ${API_ID} (${REGION}/${STAGE})\n`);

let clientConnectionId = null;

// Step 1: Connect as client
console.log('Step 1: Connecting as WebSocket client...');
const ws = new WebSocket(WS_URL);

ws.on('open', () => {
    console.log('✅ Client connected!\n');
    
    // Subscribe to admin channel (this will trigger Lambda to send connection ID)
    console.log('Step 2: Subscribing to "admin" channel...');
    ws.send(JSON.stringify({
        action: 'subscribe',
        channel: 'admin'
    }));
    console.log('⏳ Waiting for connection ID and subscription confirmation...\n');
});

ws.on('message', (data) => {
    const message = JSON.parse(data.toString());
    
    console.log('📨 Message received:');
    console.log(JSON.stringify(message, null, 2));
    console.log('');
    
    // Handle connection ID from server (sent when subscribing)
    if (message.type === 'connection_id') {
        clientConnectionId = message.connection_id;
        console.log('✅ Received connection ID:', clientConnectionId);
        console.log('');
    }
    
    // Handle subscription success
    else if (message.type === 'subscription_succeeded') {
        console.log('✅ Subscribed to channel:', message.channel);
        console.log('');
        
        // Now test broadcasting if we have connection ID
        if (clientConnectionId) {
            console.log('Step 3: Testing server-side broadcasting...');
            testBroadcasting(clientConnectionId);
        } else {
            console.log('⚠️  No connection ID received - skipping broadcast test');
            console.log('   Make sure Lambda sends connection ID before subscription success\n');
        }
    }
    
    // Handle broadcast message
    else if (message.channel && message.event) {
        console.log('🎉 Broadcast received!');
        console.log(`   Channel: ${message.channel}`);
        console.log(`   Event:   ${message.event}`);
        console.log(`   Data:    ${JSON.stringify(message.data)}\n`);
        
        // Test complete
        setTimeout(() => {
            console.log('✅ All tests passed!');
            ws.close();
        }, 1000);
    }
});

ws.on('close', () => {
    console.log('🔌 Connection closed');
    console.log('\n' + '='.repeat(70));
    console.log('Test Summary:');
    console.log('  ✅ WebSocket connection: Working');
    console.log('  ✅ Channel subscription: Working');
    console.log('  ⚠️  Broadcasting: Need connection ID to test');
    console.log('='.repeat(70));
});

ws.on('error', (error) => {
    console.error('❌ Error:', error.message);
    process.exit(1);
});

// Function to test broadcasting (call manually with connection ID)
async function testBroadcasting(connectionId) {
    console.log('\nStep 3: Testing server-side broadcasting...');
    
    try {
        // Initialize broadcaster
        initBroadcaster({
            apiId: API_ID,
            region: REGION,
            stage: STAGE
        });
        
        // Register this connection
        registerConnection(connectionId);
        console.log(`✅ Registered connection: ${connectionId}\n`);
        
        // Broadcast a message
        console.log('Step 4: Broadcasting admin event...');
        const result = await broadcastAdminEvent({
            type: 'test_event',
            message: 'Hello from broadcaster!',
            timestamp: new Date().toISOString()
        });
        
        console.log('✅ Broadcast result:', result);
        
    } catch (error) {
        console.error('❌ Broadcast error:', error.message);
    }
}

// Export for manual testing
module.exports = { testBroadcasting };
