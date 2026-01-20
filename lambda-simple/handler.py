"""
Simple WebSocket Handler for AWS API Gateway
Handles all routes in a single Lambda function
"""

import json
import boto3
import os

# API Gateway Management API client (initialized per request)
def get_api_client(domain_name, stage):
    """Create API Gateway Management API client"""
    endpoint_url = f"https://{domain_name}/{stage}"
    return boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)


def send_to_connection(client, connection_id, data):
    """Send message to a specific connection"""
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode('utf-8')
        )
        return True
    except client.exceptions.GoneException:
        print(f"Connection {connection_id} is gone")
        return False
    except Exception as e:
        print(f"Error sending to {connection_id}: {e}")
        return False


def broadcast_to_all(client, sender_id, data, exclude_sender=False):
    """
    Broadcast message to all connected clients
    
    Note: API Gateway doesn't provide a way to list all connections.
    In production, you'd need to track connections in DynamoDB or Redis.
    For this simple version, we'll just acknowledge receipt.
    """
    # Since we can't list connections without storage,
    # just echo back to sender for this simple implementation
    if not exclude_sender:
        send_to_connection(client, sender_id, data)
    
    # In a real implementation with connection tracking:
    # connections = get_all_connections_from_storage()
    # for conn_id in connections:
    #     if exclude_sender and conn_id == sender_id:
    #         continue
    #     send_to_connection(client, conn_id, data)


def lambda_handler(event, context):
    """
    Main handler for all WebSocket events
    """
    
    route_key = event['requestContext']['routeKey']
    connection_id = event['requestContext']['connectionId']
    domain_name = event['requestContext']['domainName']
    stage = event['requestContext']['stage']
    
    print(f"Route: {route_key}, Connection: {connection_id}")
    
    # Create API client
    api_client = get_api_client(domain_name, stage)
    
    # Handle routes
    if route_key == '$connect':
        # New connection
        print(f"Client connected: {connection_id}")
        return {'statusCode': 200}
    
    elif route_key == '$disconnect':
        # Connection closed
        print(f"Client disconnected: {connection_id}")
        return {'statusCode': 200}
    
    elif route_key == '$default':
        # Handle all messages
        try:
            body = json.loads(event.get('body', '{}'))
            action = body.get('action', 'unknown')
            
            print(f"Action: {action}, Data: {body}")
            
            if action == 'subscribe':
                # Subscribe to channel
                channel = body.get('channel', 'default')
                response = {
                    'type': 'subscription_succeeded',
                    'channel': channel
                }
                send_to_connection(api_client, connection_id, response)
                
            elif action == 'message':
                # Broadcast message
                # Echo back to sender (since we don't have connection list)
                response = {
                    'type': 'message',
                    'data': body.get('data', {})
                }
                send_to_connection(api_client, connection_id, response)
            
            else:
                # Unknown action
                response = {
                    'type': 'error',
                    'message': f'Unknown action: {action}'
                }
                send_to_connection(api_client, connection_id, response)
            
            return {'statusCode': 200}
            
        except Exception as e:
            print(f"Error processing message: {e}")
            return {'statusCode': 500}
    
    return {'statusCode': 404}
