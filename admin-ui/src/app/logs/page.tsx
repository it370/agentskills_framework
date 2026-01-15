"use client";

import { useEffect, useState } from "react";
import { connectLogs } from "../../lib/api";
import DashboardLayout from "../../components/DashboardLayout";

// Check which broadcaster is being used
const USE_PUSHER = process.env.NEXT_PUBLIC_USE_PUSHER === "true" || !!process.env.NEXT_PUBLIC_PUSHER_KEY;
const PUSHER_CLUSTER = process.env.NEXT_PUBLIC_PUSHER_CLUSTER || "ap2";
const BROADCASTER_NAME = USE_PUSHER ? "Pusher Channels" : "Socket.IO";
const BROADCASTER_URL = USE_PUSHER 
  ? `wss://ws-${PUSHER_CLUSTER}.pusher.com (cluster: ${PUSHER_CLUSTER})`
  : `Socket.IO (default host)`;

export default function LogsPage() {
  const [lines, setLines] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [autoscroll, setAutoscroll] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<string>("Connecting...");

  useEffect(() => {
    setConnectionStatus("Connecting...");
    
    const connection = connectLogs((line) => {
      setLines((prev) => [...prev.slice(-1000), line]);
      if (connectionStatus !== "Connected") {
        setConnectionStatus("Connected");
      }
    });
    
    // Set connected status after a short delay (waiting for Pusher subscription)
    const timer = setTimeout(() => {
      setConnectionStatus("Connected");
    }, 2000);
    
    return () => { 
      clearTimeout(timer);
      connection.disconnect(); 
    };
  }, []);

  useEffect(() => {
    if (autoscroll) {
      const el = document.getElementById("log-container");
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [lines, autoscroll]);

  const filteredLines = filter
    ? lines.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Live Logs</h1>
          <p className="mt-2 text-sm text-gray-600">
            Real-time log streaming from all workflow instances
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <input
                type="text"
                placeholder="Filter logs..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={autoscroll}
                onChange={(e) => setAutoscroll(e.target.checked)}
                className="rounded border-gray-300"
              />
              Auto-scroll
            </label>
            <button
              onClick={() => setLines([])}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors text-sm font-medium"
            >
              Clear
            </button>
            <div className="text-sm text-gray-600">
              {filteredLines.length} / {lines.length} lines
            </div>
          </div>
        </div>

        {/* Log Display */}
        <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
              </div>
              <span className="text-xs text-gray-400 ml-2">
                Streaming from {BROADCASTER_NAME} at {BROADCASTER_URL}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-full ${connectionStatus === "Connected" ? "bg-green-400 animate-pulse" : "bg-yellow-400 animate-pulse"}`}></div>
              <span className="text-xs text-gray-400">{connectionStatus}</span>
            </div>
          </div>
          <div
            id="log-container"
            className="p-4 overflow-auto font-mono text-sm text-green-400"
            style={{ height: "calc(100vh - 320px)", minHeight: "400px" }}
          >
            {filteredLines.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                {lines.length === 0 ? "Waiting for logs..." : "No matching logs"}
              </div>
            ) : (
              filteredLines.map((line, idx) => (
                <div key={idx} className="hover:bg-gray-800/50 px-2 -mx-2 rounded">
                  <span className="text-gray-500 select-none mr-4">
                    {String(idx + 1).padStart(4, " ")}
                  </span>
                  <span className="whitespace-pre-wrap break-all">{line}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
