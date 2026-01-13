"""
Simple WebSocket Test Server
Run this to test if WebSocket connections work on port 8000
"""
import asyncio
import websockets
from datetime import datetime
import json

async def handle_client(websocket, path):
    client_ip = websocket.remote_address[0]
    print(f"[{datetime.now()}] ✅ New connection from {client_ip}")
    
    try:
        # Send welcome message
        welcome = {
            "type": "connected",
            "message": "Port 8000 WebSocket is accessible!",
            "timestamp": datetime.now().isoformat(),
            "your_ip": client_ip
        }
        await websocket.send(json.dumps(welcome))
        print(f"[{datetime.now()}] 📤 Sent welcome to {client_ip}")
        
        # Echo any messages received
        async for message in websocket:
            print(f"[{datetime.now()}] 📥 Received from {client_ip}: {message}")
            
            response = {
                "type": "echo",
                "your_message": message,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(response))
            print(f"[{datetime.now()}] 📤 Echoed back to {client_ip}")
            
    except websockets.exceptions.ConnectionClosed:
        print(f"[{datetime.now()}] ❌ Connection closed by {client_ip}")
    except Exception as e:
        print(f"[{datetime.now()}] ⚠️  Error with {client_ip}: {e}")
    finally:
        print(f"[{datetime.now()}] 👋 Client {client_ip} disconnected")

async def main():
    host = "0.0.0.0"  # Listen on all interfaces
    port = 8000
    
    print("=" * 60)
    print(f"🚀 Test WebSocket Server Running")
    print("=" * 60)
    print(f"   Listening on: {host}:{port}")
    print(f"   Local test:   ws://localhost:{port}/")
    print(f"   External test: ws://YOUR_VM_IP:{port}/")
    print()
    print("   Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
