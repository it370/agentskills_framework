"""
Test/example script for pub/sub functionality.
Run this to verify your pub/sub setup is working.

Usage:
  python -m services.pubsub.test_client [publish|listen|both]
  
Or from project root:
  python services/pubsub/test_client.py [publish|listen|both]
"""

import asyncio
import time
import sys
from pathlib import Path
from threading import Event, Thread

# Add project root to path if running as script
if __name__ == '__main__':
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from services.pubsub import create_pubsub_client
from env_loader import load_env_once


def _ensure_env_loaded():
    """Ensure environment variables are loaded before running tests."""
    project_root = Path(__file__).resolve().parents[2]
    load_env_once(project_root)
    print(f"[Test] Environment loaded from: {project_root}\n")


def test_publish():
    """Test publishing messages."""
    _ensure_env_loaded()
    print("\n=== Testing Pub/Sub Publishing ===\n")
    
    # Create client
    pubsub = create_pubsub_client()
    print(f"Created client: {type(pubsub).__name__}")
    
    # Publish test messages
    for i in range(3):
        message = {
            'test_id': i,
            'message': f'Test message {i}',
            'timestamp': time.time()
        }
        
        success = pubsub.publish('test_channel', message)
        print(f"Published message {i}: {'✓' if success else '✗'}")
        time.sleep(0.5)
    
    pubsub.close()
    print("\n✓ Publishing test complete\n")


def test_listen():
    """Test listening for messages."""
    _ensure_env_loaded()
    print("\n=== Testing Pub/Sub Listening ===\n")
    
    stop_flag = Event()
    received_messages = []
    
    def on_message(payload):
        print(f"Received: {payload}")
        received_messages.append(payload)
        
        # Stop after receiving 3 messages
        if len(received_messages) >= 3:
            stop_flag.set()
    
    # Start listener in background thread
    pubsub = create_pubsub_client()
    print(f"Created client: {type(pubsub).__name__}")
    print("Listening for messages on 'test_channel' (will stop after 3 messages)...")
    print("Run test_publish() in another terminal to send messages.\n")
    
    listener_thread = Thread(
        target=lambda: pubsub.listen('test_channel', on_message, stop_flag),
        daemon=True
    )
    listener_thread.start()
    
    # Wait for messages or timeout
    listener_thread.join(timeout=30)
    
    if received_messages:
        print(f"\n✓ Received {len(received_messages)} messages")
    else:
        print("\n⚠ No messages received (timeout)")
    
    stop_flag.set()
    pubsub.close()


def test_both():
    """Test both publishing and listening simultaneously."""
    _ensure_env_loaded()
    print("\n=== Testing Pub/Sub (Publisher + Listener) ===\n")
    
    stop_flag = Event()
    received_messages = []
    
    def on_message(payload):
        print(f"  → Received: {payload}")
        received_messages.append(payload)
        
        # Stop after receiving all messages
        if len(received_messages) >= 5:
            stop_flag.set()
    
    # Start listener
    listener_client = create_pubsub_client()
    print(f"Listener client: {type(listener_client).__name__}")
    
    listener_thread = Thread(
        target=lambda: listener_client.listen('test_channel', on_message, stop_flag),
        daemon=True
    )
    listener_thread.start()
    
    # Give listener time to start
    time.sleep(0.5)
    
    # Start publishing
    publisher_client = create_pubsub_client()
    print(f"Publisher client: {type(publisher_client).__name__}")
    print("\nPublishing messages...\n")
    
    for i in range(5):
        message = {
            'test_id': i,
            'message': f'Test message {i}',
            'timestamp': time.time()
        }
        
        publisher_client.publish('test_channel', message)
        print(f"  ← Published message {i}")
        time.sleep(0.3)
    
    # Wait for all messages to be received
    listener_thread.join(timeout=5)
    
    # Cleanup
    stop_flag.set()
    listener_client.close()
    publisher_client.close()
    
    print(f"\n✓ Test complete: Published 5, Received {len(received_messages)}")
    
    if len(received_messages) == 5:
        print("✓ All messages received successfully!")
    else:
        print(f"⚠ Only received {len(received_messages)}/5 messages")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'publish':
            test_publish()
        elif command == 'listen':
            test_listen()
        elif command == 'both':
            test_both()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python test_pubsub.py [publish|listen|both]")
    else:
        print("Pub/Sub Test Script")
        print("===================\n")
        print("Commands:")
        print("  python test_pubsub.py publish  - Test publishing")
        print("  python test_pubsub.py listen   - Test listening")
        print("  python test_pubsub.py both     - Test both (recommended)")
        print("\nRunning 'both' test by default...\n")
        test_both()

