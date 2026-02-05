#!/usr/bin/env python3
"""
Test script for callback URL feature

This script demonstrates:
1. Starting a workflow with a callback URL
2. How to receive the callback
3. What payload is sent

Requirements:
- pip install fastapi uvicorn httpx
"""

import asyncio
import json
import sys
import time
from typing import Any, Dict

import httpx
import uvicorn
from fastapi import FastAPI, Request

# Configuration
API_BASE_URL = "http://localhost:8000"
CALLBACK_PORT = 9999
CALLBACK_URL = f"http://localhost:{CALLBACK_PORT}/webhook/callback"

# Create a simple webhook receiver
webhook_app = FastAPI(title="Webhook Receiver")
received_callbacks = []


@webhook_app.post("/webhook/callback")
async def receive_callback(request: Request):
    """Endpoint that receives the callback from the workflow runner"""
    payload = await request.json()
    
    print("\n" + "="*80)
    print("🎯 CALLBACK RECEIVED!")
    print("="*80)
    print(f"Thread ID: {payload.get('thread_id')}")
    print(f"Run Name: {payload.get('run_name')}")
    print(f"Status: {payload.get('status')}")
    print(f"Created At: {payload.get('created_at')}")
    print(f"Completed At: {payload.get('completed_at')}")
    
    if payload.get('error_message'):
        print(f"Error: {payload.get('error_message')}")
        print(f"Failed Skill: {payload.get('failed_skill')}")
    
    print("\nFull payload:")
    print(json.dumps(payload, indent=2))
    print("="*80 + "\n")
    
    received_callbacks.append(payload)
    
    return {"status": "received", "timestamp": time.time()}


async def start_webhook_server():
    """Start the webhook receiver server in background"""
    config = uvicorn.Config(
        webhook_app,
        host="127.0.0.1",
        port=CALLBACK_PORT,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    
    # Run server in background
    await server.serve()


async def start_workflow_with_callback(
    auth_token: str,
    thread_id: str,
    sop: str,
    initial_data: Dict[str, Any]
):
    """Start a workflow with callback URL"""
    
    print(f"\n📤 Starting workflow with callback URL: {CALLBACK_URL}")
    print(f"Thread ID: {thread_id}")
    print(f"SOP: {sop}\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/start",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={
                "thread_id": thread_id,
                "sop": sop,
                "initial_data": initial_data,
                "callback_url": CALLBACK_URL,
                "run_name": f"Test Run - {thread_id}",
                # "broadcast": true,  # Optional: Enable for real-time UI updates
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workflow started successfully!")
            print(f"Status: {result.get('status')}")
            print(f"Thread ID: {result.get('thread_id')}")
            print(f"\n⏳ Waiting for workflow to complete and callback to be invoked...")
            return result
        else:
            print(f"❌ Failed to start workflow: {response.status_code}")
            print(response.text)
            return None


async def test_callback_feature(auth_token: str):
    """Main test function"""
    
    print("\n" + "="*80)
    print("CALLBACK URL FEATURE TEST")
    print("="*80)
    print(f"Webhook receiver will listen on: {CALLBACK_URL}")
    print(f"API Base URL: {API_BASE_URL}")
    print("="*80 + "\n")
    
    # Generate a unique thread ID
    import uuid
    thread_id = f"test_callback_{uuid.uuid4().hex[:8]}"
    
    # Start the workflow
    result = await start_workflow_with_callback(
        auth_token=auth_token,
        thread_id=thread_id,
        sop="This is a test workflow to demonstrate callback functionality",
        initial_data={"test_key": "test_value", "timestamp": time.time()}
    )
    
    if not result:
        print("❌ Test failed: Could not start workflow")
        return
    
    # Wait for callback (timeout after 5 minutes)
    print("\nWaiting for callback (timeout: 5 minutes)...")
    timeout = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if received_callbacks:
            callback_data = received_callbacks[-1]
            
            print("\n" + "="*80)
            print("✅ TEST PASSED!")
            print("="*80)
            print("Callback was received successfully!")
            print(f"Status: {callback_data.get('status')}")
            print(f"Thread ID matches: {callback_data.get('thread_id') == thread_id}")
            print("="*80 + "\n")
            return
        
        await asyncio.sleep(1)
        print(".", end="", flush=True)
    
    print("\n\n❌ TEST FAILED: Callback not received within timeout period")


def print_usage():
    """Print usage instructions"""
    print("""
Usage: python test_callback_feature.py <AUTH_TOKEN>

This script will:
1. Start a webhook receiver on port 9999
2. Start a test workflow with callback URL
3. Wait for the callback to be invoked
4. Display the callback payload

Before running:
- Make sure the API server is running on http://localhost:8000
- Get an authentication token (login via /auth/login endpoint)
- Ensure port 9999 is available

Example:
    python test_callback_feature.py eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    auth_token = sys.argv[1]
    
    # Note: This is a simplified test that requires manually running
    # the webhook server and workflow in separate processes
    # For a complete test, use multiprocessing or separate terminals
    
    print("⚠️  SETUP INSTRUCTIONS:")
    print("1. In Terminal 1: Run the webhook receiver:")
    print(f"   python -m uvicorn test_callback_feature:webhook_app --port {CALLBACK_PORT}")
    print("\n2. In Terminal 2: Run the workflow starter:")
    print(f"   python -c 'import asyncio; from test_callback_feature import start_workflow_with_callback; asyncio.run(start_workflow_with_callback(\"{auth_token[:20]}...\", \"test_cb_001\", \"Test SOP\", {{\"test\": true}}))'\n")
    print("Or use the interactive Python REPL to call start_workflow_with_callback()\n")
