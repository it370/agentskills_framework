"""
Simple Backend Broadcaster - Just HTTP Calls!

No AWS SDK needed! Just call an HTTP endpoint with your access key.

Usage (Python):
    from simple_broadcaster import broadcast_admin_event
    
    broadcast_admin_event({
        'type': 'run_started',
        'thread_id': '123',
        'run_name': 'My Workflow'
    })

Usage (Node.js):
    const { broadcastAdminEvent } = require('./simple_broadcaster');
    
    await broadcastAdminEvent({
        type: 'run_started',
        thread_id: '123',
        run_name: 'My Workflow'
    });
"""

import requests
import os

# Configuration
BROADCAST_URL = os.getenv('BROADCAST_URL', 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/production/broadcast')
ACCESS_KEY = os.getenv('BROADCAST_ACCESS_KEY', 'your-secret-key-change-this')


def broadcast_message(channel, event, data):
    """
    Broadcast message to all connected clients
    
    Args:
        channel: Channel name (e.g., 'admin', 'logs')
        event: Event name (e.g., 'admin_event', 'log')
        data: Event data (dict)
    
    Returns:
        Dict with response: {'success': bool, 'sent': int, 'failed': int}
    """
    try:
        response = requests.post(
            BROADCAST_URL,
            headers={
                'Authorization': f'Bearer {ACCESS_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'channel': channel,
                'event': event,
                'data': data
            },
            timeout=10
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Broadcast error: {e}")
        return {'success': False, 'error': str(e)}


def broadcast_admin_event(data):
    """
    Shortcut to broadcast admin events
    
    Usage:
        broadcast_admin_event({
            'type': 'run_started',
            'thread_id': 'thread-123',
            'run_name': 'My Workflow'
        })
    """
    return broadcast_message('admin', 'admin_event', data)


def broadcast_log(text, thread_id=None):
    """
    Shortcut to broadcast log messages
    
    Usage:
        broadcast_log('Step completed successfully', thread_id='thread-123')
    """
    return broadcast_message('logs', 'log', {
        'text': text,
        'thread_id': thread_id
    })


# Example usage:
if __name__ == '__main__':
    # Test broadcast
    result = broadcast_admin_event({
        'type': 'test',
        'message': 'Hello from Python backend!',
        'timestamp': '2024-01-20T10:00:00Z'
    })
    
    print('Broadcast result:', result)
