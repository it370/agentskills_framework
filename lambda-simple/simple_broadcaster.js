/**
 * Simple Backend Broadcaster - Just HTTP Calls!
 * 
 * No AWS SDK needed! Just call an HTTP endpoint with your access key.
 * 
 * Usage:
 *     const { broadcastAdminEvent } = require('./simple_broadcaster');
 *     
 *     await broadcastAdminEvent({
 *         type: 'run_started',
 *         thread_id: '123',
 *         run_name: 'My Workflow'
 *     });
 */

const https = require('https');
const http = require('http');

// Configuration
const BROADCAST_URL = process.env.BROADCAST_URL || 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/production/broadcast';
const ACCESS_KEY = process.env.BROADCAST_ACCESS_KEY || 'your-secret-key-change-this';

/**
 * Broadcast message to all connected clients
 */
async function broadcastMessage(channel, event, data) {
    return new Promise((resolve, reject) => {
        const url = new URL(BROADCAST_URL);
        const isHttps = url.protocol === 'https:';
        const lib = isHttps ? https : http;
        
        const postData = JSON.stringify({
            channel: channel,
            event: event,
            data: data
        });
        
        const options = {
            hostname: url.hostname,
            port: url.port || (isHttps ? 443 : 80),
            path: url.pathname,
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${ACCESS_KEY}`,
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        };
        
        const req = lib.request(options, (res) => {
            let responseData = '';
            
            res.on('data', (chunk) => {
                responseData += chunk;
            });
            
            res.on('end', () => {
                try {
                    const result = JSON.parse(responseData);
                    resolve(result);
                } catch (e) {
                    reject(new Error(`Invalid JSON response: ${responseData}`));
                }
            });
        });
        
        req.on('error', (error) => {
            reject(error);
        });
        
        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
        
        req.setTimeout(10000); // 10 second timeout
        req.write(postData);
        req.end();
    });
}

/**
 * Shortcut to broadcast admin events
 */
async function broadcastAdminEvent(data) {
    return broadcastMessage('admin', 'admin_event', data);
}

/**
 * Shortcut to broadcast log messages
 */
async function broadcastLog(text, threadId = null) {
    return broadcastMessage('logs', 'log', {
        text: text,
        thread_id: threadId
    });
}

module.exports = {
    broadcastMessage,
    broadcastAdminEvent,
    broadcastLog
};

// Example usage:
if (require.main === module) {
    // Test broadcast
    broadcastAdminEvent({
        type: 'test',
        message: 'Hello from Node.js backend!',
        timestamp: new Date().toISOString()
    })
    .then(result => {
        console.log('Broadcast result:', result);
    })
    .catch(error => {
        console.error('Broadcast error:', error.message);
    });
}
