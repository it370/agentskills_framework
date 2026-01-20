/**
 * Simple WebSocket Handler for AWS API Gateway
 * Handles all routes in a single Lambda function
 */

const { ApiGatewayManagementApiClient, PostToConnectionCommand } = require('@aws-sdk/client-apigatewaymanagementapi');

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
        } else {
            console.error(`Error sending to ${connectionId}:`, error);
        }
        return false;
    }
}

/**
 * Main Lambda handler for all WebSocket events
 */
exports.handler = async (event, context) => {
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
            // Just accept the connection
            // We'll send the connection ID when client first subscribes
            return { statusCode: 200 };
        }
        
        else if (routeKey === '$disconnect') {
            // Connection closed
            console.log(`Client disconnected: ${connectionId}`);
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
                
                // First, send the connection ID to the client
                await sendToConnection(apiClient, connectionId, {
                    type: 'connection_id',
                    connection_id: connectionId
                });
                
                // Then send subscription confirmation
                const response = {
                    type: 'subscription_succeeded',
                    channel: channel
                };
                await sendToConnection(apiClient, connectionId, response);
            }
            
            else if (action === 'unsubscribe') {
                // Unsubscribe from channel
                const channel = body.channel || 'default';
                const response = {
                    type: 'unsubscribe_succeeded',
                    channel: channel
                };
                await sendToConnection(apiClient, connectionId, response);
            }
            
            else if (action === 'message') {
                // Echo message back (since we don't have connection list)
                const response = {
                    type: 'message',
                    data: body.data || {}
                };
                await sendToConnection(apiClient, connectionId, response);
            }
            
            else {
                // Unknown action
                const response = {
                    type: 'error',
                    message: `Unknown action: ${action}`
                };
                await sendToConnection(apiClient, connectionId, response);
            }
            
            return { statusCode: 200 };
        }
        
        // Unknown route
        return { statusCode: 404 };
        
    } catch (error) {
        console.error('Error processing message:', error);
        return { statusCode: 500 };
    }
};
