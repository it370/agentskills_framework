/**
 * Next.js API Route for Server-Sent Events via Redis
 * This allows the Next.js app to listen to Redis and stream events to clients
 * Solves the reverse proxy issue by keeping everything on port 3000
 * 
 * Place this file at: admin-ui/src/app/api/events/admin/route.ts
 */

import { NextRequest } from 'next/server';

// You'll need to install: npm install ioredis
// import Redis from 'ioredis';

export async function GET(request: NextRequest) {
  // Create a readable stream for SSE
  const encoder = new TextEncoder();
  
  const stream = new ReadableStream({
    async start(controller) {
      // Connect to Redis (use your Redis config)
      // const redis = new Redis({
      //   host: process.env.REDIS_HOST || 'localhost',
      //   port: parseInt(process.env.REDIS_PORT || '6379'),
      // });

      // Subscribe to Redis channel
      // redis.subscribe('admin_events');

      // Handle Redis messages
      // redis.on('message', (channel, message) => {
      //   try {
      //     const data = JSON.parse(message);
      //     const sseMessage = `data: ${JSON.stringify(data)}\n\n`;
      //     controller.enqueue(encoder.encode(sseMessage));
      //   } catch (error) {
      //     console.error('Error processing Redis message:', error);
      //   }
      // });

      // Handle client disconnect
      request.signal.addEventListener('abort', () => {
        // redis.disconnect();
        controller.close();
      });

      // Send keepalive every 30 seconds
      const keepaliveInterval = setInterval(() => {
        controller.enqueue(encoder.encode(': keepalive\n\n'));
      }, 30000);

      request.signal.addEventListener('abort', () => {
        clearInterval(keepaliveInterval);
      });
    },
  });

  // Return SSE response
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
