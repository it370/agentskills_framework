/**
 * Centralized WebSocket Handler with Broadcasting
 * 
 * Handles:
 * 1. WebSocket connections ($connect, $disconnect, $default)
 * 2. HTTP broadcast endpoint (for backend to trigger broadcasts)
 */

const { ApiGatewayManagementApiClient, PostToConnectionCommand } = require('@aws-sdk/client-apigatewaymanagementapi');

// In-memory connection tracking
// In production, use DynamoDB or Redis for persistence across Lambda instances
const connections = new Map(); // connectionId -> { channels: Set }

// Access key for backend authentication
const BROADCAST_ACCESS_KEY = process.env.BROADCAST_ACCESS_KEY || 'your-secret-key-change-this';

/**
 * Create API Gateway Management API client
 */
function getApiClient(domainName, stage) {
    const endpoint = `https://${domainName}/${stage}`;
    return new ApiGatewayManagementApiClient({
        endpoint: endpoint
    });
}

/**
 * Send message to a specific connection
 */
async function sendToConnection(client, connectionId, data) {
    try {
        const command = new PostToConnectionCommand({
            ConnectionId: connectionId,
            Data: JSON.stringify(data)
        });
        
        await client.send(command);
        return true;
    } catch (error) {
        if (error.name === 'GoneException') {
            console.log(`Connection ${connectionId} is gone`);
            connections.delete(connectionId);
        } else {
            console.error(`Error sending to ${connectionId}:`, error);
        }
        return false;
    }
}

/**
 * Broadcast to all connections on a channel
 */
async function broadcastToChannel(apiClient, channel, event, data, excludeConnectionId = null) {
    let sent = 0;
    let failed = 0;
    
    const message = {
        channel: channel,
        event: event,
        data: data
    };
    
    // Send to all connections subscribed to this channel
    for (const [connectionId, connData] of connections.entries()) {
        // Skip if this is the sender and we're excluding them
        if (excludeConnectionId && connectionId === excludeConnectionId) {
            continue;
        }
        
        if (connData.channels.has(channel)) {
            const success = await sendToConnection(apiClient, connectionId, message);
            if (success) sent++;
            else failed++;
        }
    }
    
    console.log(`Broadcast to '${channel}': ${sent} sent, ${failed} failed`);
    return { sent, failed };
}

/**
 * Main Lambda handler
 */
exports.handler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    // Check if this is an HTTP request (broadcast from backend)
    if (event.requestContext && event.requestContext.http) {
        return await handleHttpBroadcast(event);
    }
    
    // Otherwise, it's a WebSocket request
    return await handleWebSocket(event);
};

/**
 * Handle HTTP broadcast requests from backend
 */
async function handleHttpBroadcast(event) {
    try {
        // Validate access key
        const authHeader = event.headers?.authorization || event.headers?.Authorization;
        if (authHeader !== `Bearer ${BROADCAST_ACCESS_KEY}`) {
            return {
                statusCode: 401,
                body: JSON.stringify({ error: 'Unauthorized' })
            };
        }
        
        // Parse request body
        const body = JSON.parse(event.body || '{}');
        const channel = body.channel;
        const eventName = body.event;
        const data = body.data;
        
        if (!channel || !eventName) {
            return {
                statusCode: 400,
                body: JSON.stringify({ error: 'channel and event are required' })
            };
        }
        
        // Get API Gateway details from environment or construct from request
        const domainName = event.requestContext.domainName;
        const stage = event.requestContext.stage;
        
        // Create WebSocket API client
        const wsApiId = process.env.WEBSOCKET_API_ID;
        const wsStage = process.env.WEBSOCKET_STAGE || 'production';
        const region = process.env.AWS_REGION || 'us-east-1';
        
        const wsEndpoint = `https://${wsApiId}.execute-api.${region}.amazonaws.com/${wsStage}`;
        const apiClient = new ApiGatewayManagementApiClient({ endpoint: wsEndpoint });
        
        // Broadcast
        const result = await broadcastToChannel(apiClient, channel, eventName, data);
        
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            body: JSON.stringify({
                success: true,
                channel: channel,
                event: eventName,
                ...result
            })
        };
        
    } catch (error) {
        console.error('Error handling HTTP broadcast:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: error.message })
        };
    }
}

/**
 * Handle WebSocket requests
 */
async function handleWebSocket(event) {
    const routeKey = event.requestContext.routeKey;
    const connectionId = event.requestContext.connectionId;
    const domainName = event.requestContext.domainName;
    const stage = event.requestContext.stage;
    
    console.log(`Route: ${routeKey}, Connection: ${connectionId}`);
    
    // Create API client
    const apiClient = getApiClient(domainName, stage);
    
    try {
        // Handle routes
        if (routeKey === '$connect') {
            // New connection
            console.log(`Client connected: ${connectionId}`);
            connections.set(connectionId, { channels: new Set() });
            return { statusCode: 200 };
        }
        
        else if (routeKey === '$disconnect') {
            // Connection closed
            console.log(`Client disconnected: ${connectionId}`);
            connections.delete(connectionId);
            return { statusCode: 200 };
        }
        
        else if (routeKey === '$default') {
            // Handle all messages
            const body = JSON.parse(event.body || '{}');
            const action = body.action || 'unknown';
            
            console.log(`Action: ${action}, Data:`, body);
            
            if (action === 'subscribe') {
                // Subscribe to channel
                const channel = body.channel || 'default';
                
                // Track subscription
                if (connections.has(connectionId)) {
                    connections.get(connectionId).channels.add(channel);
                } else {
                    connections.set(connectionId, { channels: new Set([channel]) });
                }
                
                console.log(`Connection ${connectionId} subscribed to '${channel}'`);
                
                // Send connection ID first
                await sendToConnection(apiClient, connectionId, {
                    type: 'connection_id',
                    connection_id: connectionId
                });
                
                // Then send subscription confirmation
                await sendToConnection(apiClient, connectionId, {
                    type: 'subscription_succeeded',
                    channel: channel
                });
            }
            
            else if (action === 'unsubscribe') {
                // Unsubscribe from channel
                const channel = body.channel || 'default';
                
                if (connections.has(connectionId)) {
                    connections.get(connectionId).channels.delete(channel);
                }
                
                console.log(`Connection ${connectionId} unsubscribed from '${channel}'`);
                
                await sendToConnection(apiClient, connectionId, {
                    type: 'unsubscribe_succeeded',
                    channel: channel
                });
            }
            
            else if (action === 'send' || action === 'message') {
                // Send message to channel or specific connection
                const channel = body.channel;
                const targetConnectionId = body.connectionId; // Optional: send to specific client
                const event = body.event || 'message';
                const data = body.data;
                
                if (targetConnectionId) {
                    // Send to specific connection only
                    console.log(`Sending to specific connection: ${targetConnectionId}`);
                    await sendToConnection(apiClient, targetConnectionId, {
                        channel: channel,
                        event: event,
                        data: data,
                        from: connectionId
                    });
                } else if (channel) {
                    // Broadcast to all subscribers of this channel
                    console.log(`Broadcasting to channel '${channel}'`);
                    const result = await broadcastToChannel(apiClient, channel, event, data);
                    
                    // Send acknowledgment to sender
                    await sendToConnection(apiClient, connectionId, {
                        type: 'send_success',
                        channel: channel,
                        sent: result.sent,
                        failed: result.failed
                    });
                } else {
                    // No channel or connectionId specified
                    await sendToConnection(apiClient, connectionId, {
                        type: 'error',
                        message: 'Either channel or connectionId must be specified'
                    });
                }
            }
            
            else {
                // Unknown action
                await sendToConnection(apiClient, connectionId, {
                    type: 'error',
                    message: `Unknown action: ${action}`
                });
            }
            
            return { statusCode: 200 };
        }
        
        // Unknown route
        return { statusCode: 404 };
        
    } catch (error) {
        console.error('Error processing message:', error);
        return { statusCode: 500 };
    }
}
