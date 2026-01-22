/**
 * AWS AppSync Event API Client
 * 
 * Mimics Pusher's API for drop-in replacement
 * Uses AWS Amplify SDK for AppSync Events subscriptions
 */

interface AppSyncConfig {
  region: string;
  apiKey?: string;
  namespace?: string;
  enabledTransports?: string[];
  forceTLS?: boolean;
}

interface InternalChannelData {
  name: string;
  eventHandlers: Map<string, Set<(data: any) => void>>;
  subscribed: boolean;
}

interface AppSyncChannel {
  bind: (eventName: string, handler: (data: any) => void) => void;
  unbind: (eventName: string, handler?: (data: any) => void) => void;
  unbind_all: () => void;
  unsubscribe: () => void;
}

export class AppSyncClient {
  private config: AppSyncConfig & { apiUrl: string };
  private channels: Map<string, InternalChannelData> = new Map();
  private subscriptionIdsByChannel: Map<string, string> = new Map();
  private channelBySubscriptionId: Map<string, string> = new Map();
  private ws: WebSocket | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private connectionId: string | null = null;
  private isAcked = false;
  private pendingSubscriptions: Set<string> = new Set();

  // Helper to create AppSync Base64URL strings (no padding)
  private toAppSyncB64Url(obj: object): string {
    const str = JSON.stringify(obj);
    return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  private generateId(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID();
    }
    return `sub_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }

  public connection = {
    state: 'initialized',
    bind: (event: string, callback: (data?: any) => void) => {
      // Handle connection-level events
    }
  };

  constructor(apiUrl: string, config: AppSyncConfig) {
    this.config = {
      ...config,
      apiUrl
    };

    this.connect();
  }

  private connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.isAcked = false;
      // Parse host safely
      const apiUrlForParse = this.config.apiUrl.includes('://')
        ? this.config.apiUrl
        : `https://${this.config.apiUrl}`;
      const host = new URL(apiUrlForParse).host;

      if (!host) {
        console.error('[AppSync] Missing host for AppSync API URL');
        this.connection.state = 'failed';
        return;
      }

      if (!this.config.apiKey) {
        console.error('[AppSync] Missing NEXT_PUBLIC_APPSYNC_API_KEY');
        this.connection.state = 'failed';
        return;
      }

      const headerObj = {
        host,
        'x-api-key': this.config.apiKey
      };

      // Build realtime URL from Event API HTTP endpoint
      // https://<id>.appsync-api.<region>.amazonaws.com/event
      // -> wss://<id>.appsync-realtime-api.<region>.amazonaws.com/event/realtime
      const wsBase = apiUrlForParse
        .replace('https://', 'wss://')
        .replace('http://', 'wss://')
        .replace('.appsync-api.', '.appsync-realtime-api.')
        .replace(/\/event\/?$/, '/event/realtime');

      const authProtocol = `header-${this.toAppSyncB64Url(headerObj)}`;
      this.ws = new WebSocket(wsBase, ['aws-appsync-event-ws', authProtocol]);

      this.ws.onopen = () => {
        this.connection.state = 'connected';
        this.sendHandshake();

        // Resubscribe to all channels (after ack)
        this.channels.forEach((channel, channelName) => {
          if (channel.subscribed) {
            this.sendSubscribe(channelName, true);
          }
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (e) {
          console.error('[AppSync] Failed to parse message:', e);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[AppSync] WebSocket error:', error);
        this.connection.state = 'failed';
      };

      this.ws.onclose = () => {
        this.connection.state = 'disconnected';
        this.scheduleReconnect();
      };
    } catch (error) {
      console.error('[AppSync] Connection error:', error);
      this.scheduleReconnect();
    }
  }

  private sendHandshake() {
    const handshake = {
      type: 'connection_init',
      payload: {}
    };

    this.send(handshake);
  }

  private handleMessage(message: any) {
    switch (message.type) {
      case 'connection_ack':
        this.connectionId = message.payload?.connectionId;
        this.isAcked = true;

        // Flush any pending subscriptions after ack
        this.pendingSubscriptions.forEach((channelName) => {
          this.sendSubscribe(channelName, true);
        });
        this.pendingSubscriptions.clear();
        break;

      case 'connection_error':
        // Parse error structure: {"errors": [{"message": "...", "errorCode": 400}]}
        const errors = message.errors || [];
        if (errors.length > 0) {
          const errorMsg = errors[0].message || 'Unknown error';
          const errorCode = errors[0].errorCode || 'N/A';
          console.error(`[AppSync] ❌ Connection error: ${errorMsg} (code: ${errorCode})`);
        } else {
          console.error('[AppSync] ❌ Connection error:', message);
        }

        // Stop reconnecting on auth errors
        const errorStr = JSON.stringify(message);
        if (errorStr.includes('Unauthorized') || errorStr.includes('API key') || errorStr.includes('auth')) {
          console.error('[AppSync] Authentication failed. Check your NEXT_PUBLIC_APPSYNC_API_KEY');
          if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
          }
        }
        break;

      case 'subscribe_success': {
        const channelName = this.channelBySubscriptionId.get(message.id);
        const channel = channelName ? this.channels.get(channelName) : undefined;
        if (channel) {
          channel.subscribed = true;
        }
        break;
      }
      case 'subscribe_error': {
        const channelName = this.channelBySubscriptionId.get(message.id);
        console.error(
          `[AppSync] ❌ Subscribe error${channelName ? ` for '${channelName}'` : ''}:`,
          message.errors || message
        );
        break;
      }
      case 'unsubscribe_success':
        break;

      case 'data': {
        const channelName = this.channelBySubscriptionId.get(message.id);
        const targetChannel = channelName ? this.channels.get(channelName) : undefined;
        if (!targetChannel) {
          break;
        }

        const events = Array.isArray(message.event) ? message.event : [message.event];
        events.forEach((eventStr: any) => {
          try {
            const eventPayload = typeof eventStr === "string" ? JSON.parse(eventStr) : eventStr;
            const eventName = eventPayload?.event;
            const data = eventPayload?.data;
            if (!eventName) return;

            const handlers = targetChannel.eventHandlers.get(eventName);
            if (handlers) {
              handlers.forEach(handler => {
                try {
                  handler(data);
                } catch (e) {
                  console.error(`[AppSync] Error in event handler:`, e);
                }
              });
            }
          } catch (e) {
            console.error('[AppSync] Failed to parse event payload:', e);
          }
        });
        break;
      }

      case 'ka':
        // Keep-alive message
        break;

      case 'error':
        console.error('[AppSync] Server error:', message.message);
        break;
    }
  }

  private send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('[AppSync] Cannot send, WebSocket not open');
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, 3000);
  }

  private subscribeToChannel(channelName: string) {
    this.sendSubscribe(channelName, false);
  }

  private sendSubscribe(channelName: string, forceSend: boolean) {
    if (!this.config.apiKey) {
      console.error('[AppSync] Missing NEXT_PUBLIC_APPSYNC_API_KEY');
      return;
    }

    if (!this.isAcked && !forceSend) {
      this.pendingSubscriptions.add(channelName);
      return;
    }

    const apiUrlForParse = this.config.apiUrl.includes('://')
      ? this.config.apiUrl
      : `https://${this.config.apiUrl}`;
    const host = new URL(apiUrlForParse).host;
    const id = this.generateId();

    this.subscriptionIdsByChannel.set(channelName, id);
    this.channelBySubscriptionId.set(id, channelName);

    const subscribeMessage = {
      type: 'subscribe',
      id,
      channel: channelName,
      authorization: {
        host,
        'x-api-key': this.config.apiKey
      }
    };

    this.send(subscribeMessage);
  }

  subscribe(channelName: string): AppSyncChannel {
    let channelData = this.channels.get(channelName);

    if (!channelData) {
      channelData = {
        name: channelName,
        eventHandlers: new Map(),
        subscribed: false
      };
      this.channels.set(channelName, channelData);
    }

    // Send subscribe message
    this.subscribeToChannel(channelName);

    // Store reference for closures
    const self = this;
    const data = channelData;

    // Return channel object with Pusher-like API
    const channel: AppSyncChannel = {
      bind: (eventName: string, handler: (data: any) => void) => {
        if (!data.eventHandlers.has(eventName)) {
          data.eventHandlers.set(eventName, new Set());
        }

        data.eventHandlers.get(eventName)!.add(handler);
      },

      unbind: (eventName: string, handler?: (data: any) => void) => {
        if (handler) {
          data.eventHandlers.get(eventName)?.delete(handler);
        } else {
          data.eventHandlers.delete(eventName);
        }
      },

      unbind_all: () => {
        data.eventHandlers.clear();
      },

      unsubscribe: () => {
        const subscriptionId = self.subscriptionIdsByChannel.get(channelName);
        const unsubscribeMessage = {
          type: 'unsubscribe',
          id: subscriptionId || self.generateId()
        };

        self.send(unsubscribeMessage);
        data.subscribed = false;
      }
    };

    return channel;
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    // Unsubscribe from all channels
    this.channels.forEach((channel, channelName) => {
      if (channel.subscribed) {
        const subscriptionId = this.subscriptionIdsByChannel.get(channelName);
        const unsubscribeMessage = {
          type: 'unsubscribe',
          id: subscriptionId || this.generateId()
        };
        this.send(unsubscribeMessage);
      }
    });

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.connection.state = 'disconnected';
  }
}
