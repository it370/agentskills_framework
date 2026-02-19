/**
 * Global Admin Events System – SSE only.
 *
 * Opens a single persistent SSE connection to /api/admin-events/stream.
 * Components subscribe/unsubscribe to specific event types via adminEvents.on().
 */

import { getAuthHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

type EventHandler = (event: any) => void;

class AdminEventsManager {
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private initialized = false;
  private abortController: AbortController | null = null;

  initialize() {
    if (this.initialized) return;
    this.initialized = true;
    this.abortController = new AbortController();
    this.startStream();
    console.log("[AdminEvents] SSE stream initialized");
  }

  private async startStream() {
    const url = `${API_BASE}/api/admin-events/stream`;
    console.info("[AdminEvents][global] connect", { url });
    while (!this.abortController?.signal.aborted) {
      try {
        const res = await fetch(url, {
          headers: getAuthHeaders(),
          signal: this.abortController!.signal,
        });
        console.info("[AdminEvents][global] response", {
          ok: res.ok,
          status: res.status,
          statusText: res.statusText,
        });
        if (!res.ok || !res.body) {
          await this.delay(3000);
          continue;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                const event = data?.data ?? data;
                const eventType = event?.type || event?.event || "unknown";
                const eventThreadId = event?.thread_id || "n/a";
                console.info(`[AdminEvents][global] ${eventType}`, { thread_id: eventThreadId, event });
                this.dispatch(event);
              } catch (_) {}
            }
          }
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        console.warn("[AdminEvents] SSE error, reconnecting in 3s:", e);
      }
      await this.delay(3000);
    }
  }

  private delay(ms: number) {
    return new Promise<void>((resolve) => setTimeout(resolve, ms));
  }

  private dispatch(data: any) {
    const eventType = data?.type || data?.event || "unknown";
    const typeHandlers = this.handlers.get(eventType);
    if (typeHandlers) typeHandlers.forEach((h) => h(data));
    const wildcardHandlers = this.handlers.get("*");
    if (wildcardHandlers) wildcardHandlers.forEach((h) => h(data));
  }

  on(eventType: string, handler: EventHandler): () => void {
    if (!this.initialized) this.initialize();
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, new Set());
    this.handlers.get(eventType)!.add(handler);
    return () => {
      const handlers = this.handlers.get(eventType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) this.handlers.delete(eventType);
      }
    };
  }

  once(eventType: string, handler: EventHandler): () => void {
    const wrapped = (event: any) => {
      handler(event);
      unsubscribe();
    };
    const unsubscribe = this.on(eventType, wrapped);
    return unsubscribe;
  }

  disconnect() {
    this.abortController?.abort();
    this.abortController = null;
    this.handlers.clear();
    this.initialized = false;
    console.log("[AdminEvents] Disconnected");
  }
}

export const adminEvents = new AdminEventsManager();

if (typeof window !== "undefined") {
  adminEvents.initialize();
}
