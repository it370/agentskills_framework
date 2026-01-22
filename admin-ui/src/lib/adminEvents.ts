/**
 * Global Admin Events System
 * 
 * Single Pusher connection shared across the entire app.
 * Components can subscribe/unsubscribe to specific event types.
 */

import Pusher from "pusher-js";
import { getAppSyncClient } from "./realtimeClient";

const PUSHER_KEY = process.env.NEXT_PUBLIC_PUSHER_KEY || "";
const PUSHER_CLUSTER = process.env.NEXT_PUBLIC_PUSHER_CLUSTER || "ap2";
const BROADCASTER_TYPE = process.env.NEXT_PUBLIC_BROADCASTER_TYPE || "pusher";
const USE_PUSHER = BROADCASTER_TYPE.toLowerCase() !== "appsync" && (process.env.NEXT_PUBLIC_USE_PUSHER === "true" || !!PUSHER_KEY);
const APPSYNC_NAMESPACE = process.env.NEXT_PUBLIC_APPSYNC_NAMESPACE || "default";

type EventHandler = (event: any) => void;

class AdminEventsManager {
  private pusher: Pusher | null = null;
  private channel: any = null;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private initialized = false;
  private appSyncChannel: any = null;

  initialize() {
    if (this.initialized) return;

    if (BROADCASTER_TYPE.toLowerCase() === "appsync") {
      const client = getAppSyncClient();
      this.appSyncChannel = client.subscribe(`${APPSYNC_NAMESPACE}/admin`);

      this.appSyncChannel.bind("admin_event", (data: any) => {
        this.handleEvent(data, "AppSync");
      });

      this.initialized = true;
      console.log("[AdminEvents] Global AppSync connection initialized");
      return;
    }

    if (!USE_PUSHER) return;

    this.pusher = new Pusher(PUSHER_KEY, {
      cluster: PUSHER_CLUSTER,
      enabledTransports: ["ws", "wss"],
      forceTLS: true,
    });

    this.channel = this.pusher.subscribe("admin");
    this.channel.bind("admin_event", (data: any) => {
      this.handleEvent(data, "Pusher");
    });

    this.initialized = true;
    console.log("[AdminEvents] Global Pusher connection initialized");
  }

  private handleEvent(data: any, source: "Pusher" | "AppSync") {
    // console.log(`[AdminEvents] Raw event received (${source}):`, JSON.stringify(data));

    // Broadcaster wraps in {type: 'run_event', data: payload}
    const actualData = (data.type === "run_event" && data.data) ? data.data : data;
    const eventType = actualData.type || actualData.event || "unknown";

    // console.log("[AdminEvents] Unwrapped event type:", eventType, "data:", JSON.stringify(actualData));

    const typeHandlers = this.handlers.get(eventType);
    if (typeHandlers) {
      console.log(`[AdminEvents] Calling ${typeHandlers.size} handler(s) for type '${eventType}'`);
      typeHandlers.forEach(handler => handler(actualData));
    } else {
      console.log(`[AdminEvents] No handlers registered for type '${eventType}'`);
    }

    const wildcardHandlers = this.handlers.get("*");
    if (wildcardHandlers) {
      wildcardHandlers.forEach(handler => handler(actualData));
    }
  }

  /**
   * Subscribe to admin events of a specific type
   * @param eventType - Event type to listen for (e.g., 'ack', 'run_started'), or '*' for all
   * @param handler - Callback function
   * @returns Unsubscribe function
   */
  on(eventType: string, handler: EventHandler): () => void {
    if (!this.initialized) {
      this.initialize();
    }

    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }

    this.handlers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.handlers.get(eventType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.handlers.delete(eventType);
        }
      }
    };
  }

  /**
   * Subscribe to a specific one-time event (auto-unsubscribes after first call)
   */
  once(eventType: string, handler: EventHandler): () => void {
    const wrappedHandler = (event: any) => {
      handler(event);
      unsubscribe();
    };

    const unsubscribe = this.on(eventType, wrappedHandler);
    return unsubscribe;
  }

  disconnect() {
    if (this.appSyncChannel) {
      this.appSyncChannel.unbind_all?.();
      this.appSyncChannel.unsubscribe?.();
      this.appSyncChannel = null;
    }

    if (this.pusher) {
      this.pusher.disconnect();
      this.pusher = null;
      this.channel = null;
      this.handlers.clear();
      this.initialized = false;
      console.log("[AdminEvents] Pusher connection closed");
    }
  }
}

// Global singleton instance
export const adminEvents = new AdminEventsManager();

// Auto-initialize on client side
if (typeof window !== 'undefined') {
  adminEvents.initialize();
}
