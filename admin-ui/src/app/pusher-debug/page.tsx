"use client";

import { useEffect, useState } from "react";
import Pusher from "pusher-js";

export default function PusherDebugPage() {
  const [messages, setMessages] = useState<string[]>([]);
  const [config, setConfig] = useState({
    key: "",
    cluster: "",
    configured: false
  });

  useEffect(() => {
    // Get config from env
    const key = process.env.NEXT_PUBLIC_PUSHER_KEY || "";
    const cluster = process.env.NEXT_PUBLIC_PUSHER_CLUSTER || "ap2";
    
    setConfig({
      key: key ? `${key.substring(0, 10)}...${key.substring(key.length - 4)}` : "NOT SET",
      cluster,
      configured: !!key
    });

    if (!key) {
      addMessage("❌ ERROR: NEXT_PUBLIC_PUSHER_KEY not set in .env.local");
      return;
    }

    addMessage("🔧 Initializing Pusher...");
    addMessage(`   Key: ${key.substring(0, 10)}...`);
    addMessage(`   Cluster: ${cluster}`);

    // Enable Pusher debug logging
    Pusher.logToConsole = true;

    const pusher = new Pusher(key, {
      cluster: cluster,
      enabledTransports: ['ws', 'wss'],
      forceTLS: true,
    });

    pusher.connection.bind('connecting', () => {
      addMessage("🔄 Connecting to Pusher...");
    });

    pusher.connection.bind('connected', () => {
      addMessage("✅ Connected to Pusher WebSocket!");
    });

    pusher.connection.bind('error', (err: any) => {
      addMessage(`❌ Connection error: ${JSON.stringify(err)}`);
    });

    pusher.connection.bind('unavailable', () => {
      addMessage("❌ Connection unavailable");
    });

    pusher.connection.bind('failed', () => {
      addMessage("❌ Connection failed");
    });

    // Subscribe to logs channel
    addMessage("📡 Subscribing to 'logs' channel...");
    const logsChannel = pusher.subscribe('logs');

    logsChannel.bind('pusher:subscription_succeeded', () => {
      addMessage("✅ Successfully subscribed to 'logs' channel!");
      addMessage("   Waiting for messages...");
    });

    logsChannel.bind('pusher:subscription_error', (error: any) => {
      addMessage(`❌ Subscription error: ${JSON.stringify(error)}`);
    });

    logsChannel.bind('log', (data: any) => {
      addMessage(`🎉 LOG MESSAGE RECEIVED: ${JSON.stringify(data)}`);
    });

    // Subscribe to admin channel
    addMessage("📡 Subscribing to 'admin' channel...");
    const adminChannel = pusher.subscribe('admin');

    adminChannel.bind('pusher:subscription_succeeded', () => {
      addMessage("✅ Successfully subscribed to 'admin' channel!");
      addMessage("   Waiting for messages...");
    });

    adminChannel.bind('pusher:subscription_error', (error: any) => {
      addMessage(`❌ Admin subscription error: ${JSON.stringify(error)}`);
    });

    adminChannel.bind('admin_event', (data: any) => {
      addMessage(`🎉 ADMIN EVENT RECEIVED: ${JSON.stringify(data)}`);
    });

    // Also bind to ALL events for debugging
    logsChannel.bind_global((eventName: string, data: any) => {
      if (!eventName.startsWith('pusher:')) {
        addMessage(`📨 Event on logs channel: ${eventName} - ${JSON.stringify(data)}`);
      }
    });

    adminChannel.bind_global((eventName: string, data: any) => {
      if (!eventName.startsWith('pusher:')) {
        addMessage(`📨 Event on admin channel: ${eventName} - ${JSON.stringify(data)}`);
      }
    });

    return () => {
      addMessage("🔌 Disconnecting...");
      logsChannel.unbind_all();
      logsChannel.unsubscribe();
      adminChannel.unbind_all();
      adminChannel.unsubscribe();
      pusher.disconnect();
    };
  }, []);

  const addMessage = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages((prev) => [...prev, `[${timestamp}] ${msg}`]);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Pusher Debug Console</h1>
        <p className="text-sm text-gray-600 mb-8">
          Test your Pusher connection and see real-time messages
        </p>

        {/* Configuration Display */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Configuration</h2>
          <div className="space-y-2 font-mono text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Pusher Key:</span>
              <span className={config.configured ? "text-green-600" : "text-red-600"}>
                {config.key}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Cluster:</span>
              <span className="text-gray-900">{config.cluster}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Status:</span>
              <span className={config.configured ? "text-green-600" : "text-red-600"}>
                {config.configured ? "✅ Configured" : "❌ Not Configured"}
              </span>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
          <h3 className="font-semibold text-blue-900 mb-2">How to Test:</h3>
          <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800">
            <li>Go to your Pusher dashboard: <a href="https://dashboard.pusher.com" target="_blank" rel="noopener" className="underline">dashboard.pusher.com</a></li>
            <li>Select your app</li>
            <li>Go to "Debug Console" tab</li>
            <li>Send a test event:
              <ul className="list-disc list-inside ml-6 mt-1">
                <li>Channel: <code className="bg-blue-100 px-1 rounded">logs</code></li>
                <li>Event: <code className="bg-blue-100 px-1 rounded">log</code></li>
                <li>Data: <code className="bg-blue-100 px-1 rounded">{`{"text": "Test message", "level": "INFO"}`}</code></li>
              </ul>
            </li>
            <li>Watch for the message to appear below!</li>
          </ol>
        </div>

        {/* Messages Log */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
              </div>
              <span className="text-xs text-gray-400 ml-2">
                Pusher Debug Log
              </span>
            </div>
            <button
              onClick={() => setMessages([])}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs transition-colors"
            >
              Clear
            </button>
          </div>
          <div
            className="p-4 overflow-auto font-mono text-sm text-green-400"
            style={{ height: "500px" }}
          >
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                Waiting for events...
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className="hover:bg-gray-800/50 px-2 -mx-2 rounded mb-1">
                  {msg}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Browser Console Reminder */}
        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">
            💡 <strong>Tip:</strong> Also check your browser console (F12) for detailed Pusher logs!
          </p>
        </div>
      </div>
    </div>
  );
}
