/**
 * Dynamic URL configuration
 * Determines protocol and domain based on current page URL
 * Supports both port-based and host-based configuration
 * 
 * Environment variables:
 * - NEXT_PUBLIC_API_PORT: Port number for API (default: 8000)
 * - NEXT_PUBLIC_WS_PORT: Port number for WebSocket (default: same as API_PORT)
 * - NEXT_PUBLIC_API_HOST: API host - use "dynamic" for auto-detection or specify a host
 * - NEXT_PUBLIC_WS_HOST: WebSocket host - use "dynamic" for auto-detection or specify a host
 */

function isLocalhost(hostname: string): boolean {
  return hostname === 'localhost' || hostname.startsWith('127.');
}

function buildUrl(port: string, protocol: 'http' | 'ws', configuredHost?: string): string {
  // If host is explicitly configured and not "dynamic", use it directly
  if (configuredHost && configuredHost.toLowerCase() !== 'dynamic') {
    // Check if the configured host already includes protocol
    if (configuredHost.startsWith('http://') || configuredHost.startsWith('https://') ||
        configuredHost.startsWith('ws://') || configuredHost.startsWith('wss://')) {
      // Host includes protocol, return as-is (ignore port and protocol params)
      return configuredHost.replace(/\/$/, '');
    }
    // Host doesn't include protocol, determine protocol based on host type
    const isLocal = isLocalhost(configuredHost);
    const finalProtocol = isLocal ? protocol : (protocol === 'http' ? 'https' : 'wss');
    return `${finalProtocol}://${configuredHost}:${port}`;
  }

  // Dynamic mode: detect from current page URL
  // Server-side rendering fallback
  if (typeof window === 'undefined') {
    return `${protocol}://localhost:${port}`;
  }

  const hostname = window.location.hostname;
  const isLocal = isLocalhost(hostname);
  
  // Determine protocol
  const finalProtocol = isLocal ? protocol : (protocol === 'http' ? 'https' : 'wss');
  
  // Use current hostname
  return `${finalProtocol}://${hostname}:${port}`;
}

export function getApiBase(): string {
  const port = process.env.NEXT_PUBLIC_API_PORT || '8000';
  const host = process.env.NEXT_PUBLIC_API_HOST;
  return buildUrl(port, 'http', host);
}

export function getWsBase(): string {
  const port = process.env.NEXT_PUBLIC_WS_PORT || process.env.NEXT_PUBLIC_API_PORT || '8000';
  const host = process.env.NEXT_PUBLIC_WS_HOST || process.env.NEXT_PUBLIC_API_HOST;
  return buildUrl(port, 'ws', host);
}
