/**
 * Alternative to WebSocket using Server-Sent Events (SSE)
 * Better for reverse proxy scenarios and simpler to configure
 */

import { RunEvent } from "./types";
import { getApiBase } from "./config";

const API_BASE = getApiBase();

/**
 * Connect to admin events using SSE instead of WebSocket
 * SSE works over regular HTTP and is easier to proxy
 */
export function connectAdminEventsSSE(onEvent: (event: RunEvent) => void): EventSource {
  const eventSource = new EventSource(`${API_BASE}/sse/admin`);

  eventSource.onmessage = (evt) => {
    try {
      const parsed = JSON.parse(evt.data);
      if (parsed?.type === "run_event") {
        onEvent(parsed.data as RunEvent);
      }
    } catch (e) {
      console.warn("Failed to parse admin event", e);
    }
  };

  eventSource.onerror = (err) => {
    console.error("[SSE] Connection error:", err);
  };

  return eventSource;
}

/**
 * Connect to logs using SSE
 */
export function connectLogsSSE(onLog: (line: string, threadId?: string) => void): EventSource {
  const eventSource = new EventSource(`${API_BASE}/sse/logs`);

  eventSource.onopen = () => {
    console.log("[SSE] Logs connection opened");
  };

  eventSource.onmessage = (evt) => {
    try {
      const parsed = JSON.parse(evt.data);
      if (parsed.text !== undefined) {
        onLog(parsed.text, parsed.thread_id);
        return;
      }
    } catch {
      // Plain text format
      onLog(evt.data as string);
    }
  };

  eventSource.onerror = (err) => {
    console.error("[SSE] Logs connection error:", err);
  };

  return eventSource;
}

/**
 * Polling-based alternative for environments that don't support SSE/WebSocket
 */
export class PollingConnection {
  private intervalId?: NodeJS.Timeout;
  private lastEventId?: string;

  constructor(
    private endpoint: string,
    private onEvent: (event: any) => void,
    private intervalMs: number = 2000
  ) {}

  start() {
    this.poll(); // Initial poll
    this.intervalId = setInterval(() => this.poll(), this.intervalMs);
  }

  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = undefined;
    }
  }

  private async poll() {
    try {
      const url = this.lastEventId
        ? `${this.endpoint}?since=${this.lastEventId}`
        : this.endpoint;

      const response = await fetch(url);
      if (!response.ok) return;

      const events = await response.json();
      
      if (Array.isArray(events)) {
        events.forEach((event) => {
          this.onEvent(event);
          if (event.id) {
            this.lastEventId = event.id;
          }
        });
      }
    } catch (error) {
      console.error("[Polling] Error:", error);
    }
  }
}

/**
 * Auto-detecting connection that tries WebSocket, falls back to SSE, then polling
 */
export function createRealtimeConnection(
  type: 'admin' | 'logs',
  onEvent: (event: any) => void
): { close: () => void } {
  const wsSupported = typeof WebSocket !== 'undefined';
  const sseSupported = typeof EventSource !== 'undefined';

  if (wsSupported) {
    try {
      // Try WebSocket first
      const { connectAdminEvents, connectLogs } = require('./api');
      const ws = type === 'admin' ? connectAdminEvents(onEvent) : connectLogs(onEvent);
      
      // If WebSocket fails, fall back
      ws.onerror = () => {
        console.log('[WebSocket] Failed, falling back to SSE...');
        ws.close();
        return createSSEConnection(type, onEvent);
      };
      
      return { close: () => ws.close() };
    } catch {
      // Fall through to SSE
    }
  }

  return createSSEConnection(type, onEvent);
}

function createSSEConnection(type: 'admin' | 'logs', onEvent: (event: any) => void) {
  if (typeof EventSource !== 'undefined') {
    try {
      const es = type === 'admin' 
        ? connectAdminEventsSSE(onEvent)
        : connectLogsSSE(onEvent);
      
      // If SSE fails, fall back to polling
      es.onerror = () => {
        console.log('[SSE] Failed, falling back to polling...');
        es.close();
        return createPollingConnection(type, onEvent);
      };
      
      return { close: () => es.close() };
    } catch {
      // Fall through to polling
    }
  }

  return createPollingConnection(type, onEvent);
}

function createPollingConnection(type: 'admin' | 'logs', onEvent: (event: any) => void) {
  const endpoint = `${API_BASE}/poll/${type}`;
  const poller = new PollingConnection(endpoint, onEvent);
  poller.start();
  
  return { close: () => poller.stop() };
}
