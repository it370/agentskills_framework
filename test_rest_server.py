"""
Simple HTTP REST API Test Server
Run this to test if port 8000 is accessible from outside
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Log the request
        print(f"[{datetime.now()}] GET {self.path} from {self.client_address[0]}")
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "status": "success",
            "message": "Port 8000 REST API is accessible!",
            "timestamp": datetime.now().isoformat(),
            "your_ip": self.client_address[0],
            "path": self.path
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == "__main__":
    host = "0.0.0.0"  # Listen on all interfaces
    port = 8000
    
    server = HTTPServer((host, port), TestHandler)
    
    print("=" * 60)
    print(f"🚀 Test REST API Server Running")
    print("=" * 60)
    print(f"   Listening on: {host}:{port}")
    print(f"   Local test:   http://localhost:{port}/")
    print(f"   External test: http://YOUR_VM_IP:{port}/")
    print()
    print("   Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
        server.shutdown()
