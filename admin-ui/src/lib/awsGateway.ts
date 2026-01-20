/**
 * Simple AWS API Gateway WebSocket Client
 * Drop-in replacement for Pusher with minimal complexity
 */

type EventHandler = (data: any) => void;

interface GatewayOptions {
  cluster?: string;
  region?: string;
  enabledTransports?: string[];
  forceTLS?: boolean;
}

class GatewayChannel {
  private name: string;
  private gateway: AWSGateway;
  private eventHandlers: Map<string, Set<EventHandler>> = new Map();

  constructor(name: string, gateway: AWSGateway) {
    this.name = name;
    this.gateway = gateway;
  }

  bind(eventName: string, callback: EventHandler): void {
    if (!this.eventHandlers.has(eventName)) {
      this.eventHandlers.set(eventName, new Set());
    }
    this.eventHandlers.get(eventName)!.add(callback);
  }

  unbind(eventName?: string, callback?: EventHandler): void {
    if (!eventName) {
      this.eventHandlers.clear();
      return;
    }
    if (!callback) {
      this.eventHandlers.delete(eventName);
      return;
    }
    const handlers = this.eventHandlers.get(eventName);
    if (handlers) {
      handlers.delete(callback);
    }
  }

  unbind_all(): void {
    this.eventHandlers.clear();
  }

  unsubscribe(): void {
    this.gateway.unsubscribe(this.name);
  }

  _trigger(eventName: string, data: any): void {
    const handlers = this.eventHandlers.get(eventName);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (e) {
          console.error(`[Gateway] Error in handler:`, e);
        }
      });
    }
  }

  getName(): string {
    return this.name;
  }
}

class GatewayConnection {
  private gateway: AWSGateway;
  private eventHandlers: Map<string, Set<EventHandler>> = new Map();
  public state: string = 'initialized';

  constructor(gateway: AWSGateway) {
    this.gateway = gateway;
  }

  bind(eventName: string, callback: EventHandler): void {
    if (!this.eventHandlers.has(eventName)) {
      this.eventHandlers.set(eventName, new Set());
    }
    this.eventHandlers.get(eventName)!.add(callback);
  }

  unbind(eventName?: string, callback?: EventHandler): void {
    if (!eventName) {
      this.eventHandlers.clear();
      return;
    }
    if (!callback) {
      this.eventHandlers.delete(eventName);
      return;
    }
    const handlers = this.eventHandlers.get(eventName);
    if (handlers) {
      handlers.delete(callback);
    }
  }

  _trigger(eventName: string, data?: any): void {
    const handlers = this.eventHandlers.get(eventName);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (e) {
          console.error(`[Gateway] Error in connection handler:`, e);
        }
      });
    }
  }

  _updateState(newState: string): void {
    const oldState = this.state;
    this.state = newState;
    this._trigger('state_change', { previous: oldState, current: newState });
  }
}

export class AWSGateway {
  private ws: WebSocket | null = null;
  private channels: Map<string, GatewayChannel> = new Map();
  private reconnectTimer: any = null;
  private reconnectAttempts: number = 0;
  private isIntentionalClose: boolean = false;
  private wsUrl: string;
  public connection: GatewayConnection;

  constructor(apiKey: string, options: GatewayOptions = {}) {
    // apiKey is the full WebSocket URL
    this.wsUrl = apiKey.startsWith('ws://') || apiKey.startsWith('wss://') 
      ? apiKey 
      : `wss://${apiKey}.execute-api.${options.region || options.cluster || 'us-east-1'}.amazonaws.com/production`;
    
    this.connection = new GatewayConnection(this);
    this._connect();
  }

  private _connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    console.log(`[Gateway] Connecting to ${this.wsUrl}...`);
    this.connection._updateState('connecting');

    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        console.log('[Gateway] Connected');
        this.connection._updateState('connected');
        this.reconnectAttempts = 0;
        this.connection._trigger('connected');

        // Resubscribe to all channels
        this.channels.forEach((channel) => {
          this._sendSubscribe(channel.getName());
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this._handleMessage(message);
        } catch (e) {
          console.error('[Gateway] Failed to parse message:', e);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[Gateway] WebSocket error:', error);
        this.connection._updateState('failed');
        this.connection._trigger('error', error);
      };

      this.ws.onclose = (event) => {
        console.log(`[Gateway] Disconnected (code: ${event.code})`);
        this.connection._updateState('disconnected');
        this.connection._trigger('disconnected');

        if (!this.isIntentionalClose) {
          this._scheduleReconnect();
        }
      };
    } catch (e) {
      console.error('[Gateway] Failed to create WebSocket:', e);
      this.connection._updateState('failed');
      this._scheduleReconnect();
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= 10) {
      console.error('[Gateway] Max reconnection attempts reached');
      this.connection._updateState('failed');
      return;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectAttempts++;
    const delay = 3000;
    console.log(`[Gateway] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})...`);
    this.connection._updateState('reconnecting');

    this.reconnectTimer = setTimeout(() => {
      this._connect();
    }, delay);
  }

  private _send(data: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[Gateway] WebSocket not ready');
      return;
    }

    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      this.ws.send(message);
    } catch (e) {
      console.error('[Gateway] Failed to send message:', e);
    }
  }

  private _sendSubscribe(channelName: string): void {
    this._send({
      action: 'subscribe',
      channel: channelName,
    });
  }

  private _handleMessage(message: any): void {
    console.log('[Gateway] Received:', message);

    // Handle subscription confirmation
    if (message.type === 'subscription_succeeded') {
      const channelName = message.channel;
      console.log(`[Gateway] Subscribed to '${channelName}'`);
      return;
    }

    // Handle errors
    if (message.type === 'error') {
      console.error('[Gateway] Server error:', message);
      return;
    }

    // Handle channel messages
    // Expected format: { channel: 'admin', event: 'admin_event', data: {...} }
    if (message.channel && message.event) {
      const channel = this.channels.get(message.channel);
      if (channel) {
        channel._trigger(message.event, message.data);
      }
    }

    // Handle pusher:subscription_error (for compatibility)
    if (message.event === 'pusher:subscription_error') {
      const channel = this.channels.get(message.channel);
      if (channel) {
        channel._trigger('pusher:subscription_error', message.data);
      }
    }
  }

  subscribe(channelName: string): GatewayChannel {
    if (this.channels.has(channelName)) {
      return this.channels.get(channelName)!;
    }

    console.log(`[Gateway] Subscribing to '${channelName}'`);
    const channel = new GatewayChannel(channelName, this);
    this.channels.set(channelName, channel);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this._sendSubscribe(channelName);
    }

    return channel;
  }

  unsubscribe(channelName: string): void {
    const channel = this.channels.get(channelName);
    if (!channel) return;

    console.log(`[Gateway] Unsubscribing from '${channelName}'`);
    channel.unbind_all();
    this.channels.delete(channelName);

    this._send({
      action: 'unsubscribe',
      channel: channelName,
    });
  }

  channel(channelName: string): GatewayChannel | undefined {
    return this.channels.get(channelName);
  }

  disconnect(): void {
    console.log('[Gateway] Disconnecting...');
    this.isIntentionalClose = true;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.channels.forEach((channel, name) => {
      this.unsubscribe(name);
    });

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.connection._updateState('disconnected');
  }
}

export default AWSGateway;
