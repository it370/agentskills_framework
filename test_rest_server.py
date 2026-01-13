"""
Combined Test Server
- REST API on port 8000
- Serves HTML page at /test that connects to WebSocket on port 8001
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[{datetime.now()}] GET {self.path} from {self.client_address[0]}")
        
        if self.path == '/test' or self.path == '/test/':
            # Serve the WebSocket test HTML page
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            html = '''<!DOCTYPE html>
<html>
<head>
    <title>Port 8000 & 8001 Test</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 900px; 
            margin: 50px auto; 
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { 
            color: #333; 
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .section {
            margin: 30px 0;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 5px;
            border-left: 4px solid #2196F3;
        }
        button { 
            padding: 12px 24px; 
            margin: 5px; 
            font-size: 16px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover { background: #45a049; }
        button:disabled { 
            background: #ccc; 
            cursor: not-allowed;
        }
        .status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin-left: 10px;
        }
        .connected { background: #4CAF50; color: white; }
        .disconnected { background: #f44336; color: white; }
        #log { 
            margin-top: 20px; 
            padding: 15px; 
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 5px;
            min-height: 200px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }
        .log-success { color: #155724; background: #d4edda; padding: 5px; margin: 2px 0; border-radius: 3px; }
        .log-error { color: #721c24; background: #f8d7da; padding: 5px; margin: 2px 0; border-radius: 3px; }
        .log-info { color: #004085; background: #cce5ff; padding: 5px; margin: 2px 0; border-radius: 3px; }
        input { 
            padding: 8px; 
            border: 1px solid #ddd; 
            border-radius: 4px;
            font-size: 14px;
            width: 300px;
        }
        .success-banner {
            background: #d4edda;
            border: 2px solid #28a745;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            color: #155724;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔌 Port 8000 (REST) & 8001 (WebSocket) Test</h1>
        
        <div class="success-banner">
            ✅ <strong>REST API (port 8000) is working!</strong><br>
            You're seeing this page, which means port 8000 is accessible.
        </div>
        
        <div class="section">
            <h2>WebSocket Test (Port 8001)</h2>
            <p>Host: <input id="host" value="localhost:8001" placeholder="e.g., localhost:8001 or YOUR_VM_IP:8001"></p>
            <button onclick="connect()" id="connectBtn">Connect WebSocket</button>
            <button onclick="send()" id="sendBtn" disabled>Send Test Message</button>
            <button onclick="disconnect()" id="disconnectBtn" disabled>Disconnect</button>
            <span class="status disconnected" id="status">Disconnected</span>
            
            <div id="log"></div>
        </div>

        <div class="section" style="border-left-color: #FF9800;">
            <h2>📋 Instructions</h2>
            <ol>
                <li><strong>Port 8000 (REST):</strong> Already working! You're viewing this page.</li>
                <li><strong>Port 8001 (WebSocket):</strong> 
                    <ul>
                        <li>Run: <code>python test_websocket_server_8001.py</code></li>
                        <li>Click "Connect WebSocket" button above</li>
                    </ul>
                </li>
                <li><strong>Test externally:</strong> Change "localhost" to your VM's public IP</li>
            </ol>
            
            <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">
                <strong>⚠️ If localhost works but external IP doesn't:</strong><br>
                Your cloud security group needs to allow ports 8000 and 8001!
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        
        function log(msg, type = 'info') {
            const div = document.getElementById('log');
            const time = new Date().toLocaleTimeString();
            const className = type === 'error' ? 'log-error' : (type === 'success' ? 'log-success' : 'log-info');
            const logEntry = document.createElement('div');
            logEntry.className = className;
            logEntry.textContent = `[${time}] ${msg}`;
            div.appendChild(logEntry);
            div.scrollTop = div.scrollHeight;
        }
        
        function updateStatus(connected) {
            const status = document.getElementById('status');
            status.textContent = connected ? 'Connected' : 'Disconnected';
            status.className = 'status ' + (connected ? 'connected' : 'disconnected');
            
            document.getElementById('connectBtn').disabled = connected;
            document.getElementById('sendBtn').disabled = !connected;
            document.getElementById('disconnectBtn').disabled = !connected;
        }
        
        function connect() {
            const host = document.getElementById('host').value.trim();
            if (!host) {
                log('❌ Please enter a host!', 'error');
                return;
            }
            
            const url = `ws://${host}/`;
            log(`🔌 Connecting to ${url}...`, 'info');
            
            try {
                ws = new WebSocket(url);
                
                ws.onopen = () => {
                    log('✅ WebSocket connected successfully!', 'success');
                    updateStatus(true);
                };
                
                ws.onmessage = (event) => {
                    log('📩 Received: ' + event.data, 'success');
                };
                
                ws.onerror = (error) => {
                    log('❌ WebSocket error occurred', 'error');
                };
                
                ws.onclose = () => {
                    log('🔌 WebSocket disconnected', 'info');
                    updateStatus(false);
                };
            } catch (error) {
                log('❌ Failed to create WebSocket: ' + error.message, 'error');
            }
        }
        
        function send() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                const msg = 'Test message at ' + new Date().toLocaleTimeString();
                ws.send(msg);
                log('📤 Sent: ' + msg, 'info');
            } else {
                log('❌ WebSocket not connected!', 'error');
            }
        }
        
        function disconnect() {
            if (ws) {
                ws.close();
            }
        }
        
        // Log initial page load
        log('✅ REST API (port 8000) is accessible!', 'success');
        log('ℹ️ Ready to test WebSocket (port 8001)', 'info');
    </script>
</body>
</html>'''
            self.wfile.write(html.encode())
            
        else:
            # Regular API response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "status": "success",
                "message": "Port 8000 REST API is accessible!",
                "timestamp": datetime.now().isoformat(),
                "your_ip": self.client_address[0],
                "path": self.path,
                "instructions": {
                    "test_page": "Visit http://localhost:8000/test to test WebSocket on port 8001"
                }
            }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    
    server = HTTPServer((host, port), TestHandler)
    
    print("=" * 70)
    print(f"🚀 REST API Test Server Running on Port {port}")
    print("=" * 70)
    print(f"   Listening on: {host}:{port}")
    print(f"   Test page:    http://localhost:{port}/test")
    print(f"   External:     http://YOUR_VM_IP:{port}/test")
    print()
    print("   Next: Run WebSocket server on port 8001:")
    print("   python test_websocket_server_8001.py")
    print()
    print("   Press Ctrl+C to stop")
    print("=" * 70)
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
        server.shutdown()
