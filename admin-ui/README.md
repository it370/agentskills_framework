# Admin UI

This is the administrative interface for the AgentSkills Framework, built with Next.js 14, React, and TypeScript.

## Features

- **Workflow Management**: View and manage workflow runs
- **Skill Management**: Create, edit, and manage skills
- **Live Logs**: Real-time log streaming from all workflow instances
- **Run Details**: View detailed information about workflow runs and their execution

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

1. Install dependencies:

```bash
npm install
```

2. Configure environment variables:

Create a `.env` file in the `admin-ui` directory:

### Port-Based Configuration

Configure port numbers in the `.env` file:

```env
NEXT_PUBLIC_API_PORT=8000
NEXT_PUBLIC_WS_PORT=8000
```

### Host Configuration

You can also configure hosts explicitly:

```env
# Dynamic mode (default) - automatically detects from page URL
NEXT_PUBLIC_API_HOST=dynamic
NEXT_PUBLIC_WS_HOST=dynamic

# Or specify a custom host
NEXT_PUBLIC_API_HOST=api.example.com
NEXT_PUBLIC_WS_HOST=ws.example.com

# Or provide a complete URL
NEXT_PUBLIC_API_HOST=https://api.example.com
NEXT_PUBLIC_WS_HOST=wss://ws.example.com
```

### Automatic Protocol and Domain Detection

**Dynamic Mode (default):**

The application automatically determines the protocol and domain based on the current page URL:

**For Local Development (localhost or 127.x.x.x):**
- API Base: `http://localhost:8000`
- WebSocket Base: `ws://localhost:8000`

**For Production (any other domain or IP):**
- API Base: `https://your-domain:8000`
- WebSocket Base: `wss://your-domain:8000`

**Custom Host Mode:**

When you specify a custom host, the system:
1. If the host includes a protocol (e.g., `https://api.example.com`), uses it as-is
2. If the host is just a domain/IP (e.g., `api.example.com`), automatically selects:
   - `http://` or `ws://` for localhost/127.x.x.x
   - `https://` or `wss://` for other domains

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

Build for production:

```bash
npm run build
```

### Start Production Server

```bash
npm start
```

## Configuration

The Admin UI uses a dynamic URL configuration system that automatically determines the correct protocol and domain based on the current page URL.

### Environment Variables

- `NEXT_PUBLIC_API_PORT`: The port number for the API server (default: 8000)
- `NEXT_PUBLIC_WS_PORT`: The port number for WebSocket connections (default: same as API port)
- `NEXT_PUBLIC_API_HOST`: Host for API - "dynamic" for auto-detection or specify a host (default: dynamic)
- `NEXT_PUBLIC_WS_HOST`: Host for WebSocket - "dynamic" for auto-detection or specify a host (default: dynamic)

### Automatic Protocol Detection

- **Local Development** (localhost or 127.x.x.x): Uses `http://` and `ws://`
- **Production** (any other domain): Uses `https://` and `wss://`

### Host Configuration

You can configure hosts in two ways:

1. **Dynamic mode** (default): Set to `"dynamic"` or leave unset
   - Automatically uses the current page's hostname
   - Adapts to any deployment environment

2. **Custom host**: Specify a specific domain or IP
   - Example: `NEXT_PUBLIC_API_HOST=api.example.com`
   - Example: `NEXT_PUBLIC_API_HOST=https://api.example.com`

This means you don't need to configure different URLs for development and production environments. The application automatically adapts based on where it's running.

For more details, see [CONFIG.md](./CONFIG.md).

## Project Structure

```
admin-ui/
├── src/
│   ├── app/                 # Next.js app directory
│   │   ├── admin/          # Admin-specific pages
│   │   ├── logs/           # Live log viewer
│   │   ├── runs/           # Workflow run management
│   │   ├── skills/         # Skill management
│   │   └── workflows/      # Workflow pages
│   ├── components/         # Reusable React components
│   │   ├── DashboardLayout.tsx
│   │   └── PythonEditor.tsx
│   └── lib/               # Utility libraries
│       ├── api.ts         # API client functions
│       ├── config.ts      # Dynamic URL configuration
│       └── types.ts       # TypeScript type definitions
├── public/                # Static assets
├── .env                   # Environment variables (not committed)
├── .env.example           # Example environment variables
├── CONFIG.md              # Configuration documentation
└── README.md              # This file
```

## API Integration

The Admin UI communicates with the AgentSkills Framework API using:

- **REST API**: For fetching and managing data
- **WebSocket**: For real-time updates and log streaming

All API calls are centralized in `src/lib/api.ts` for easy maintenance.

## Development Tips

### Hot Reload

The development server supports hot reload. Changes to files will automatically update in the browser.

### Type Safety

The project uses TypeScript for type safety. Type definitions are in `src/lib/types.ts`.

### Styling

The project uses Tailwind CSS for styling. Configuration is in `tailwind.config.ts`.

## Deployment

The application can be deployed to any platform that supports Next.js:

- Vercel (recommended)
- Netlify
- AWS
- Docker
- Self-hosted

Make sure to set the environment variables in your deployment platform.

## Troubleshooting

### WebSocket Connection Issues

If you're having issues with WebSocket connections:

1. Check that the API server is running and accessible
2. Verify the `NEXT_PUBLIC_WS_PORT` is correct
3. Check browser console for connection errors
4. Ensure your firewall/proxy allows WebSocket connections

### API Connection Issues

If API calls are failing:

1. Check that the API server is running
2. Verify the `NEXT_PUBLIC_API_PORT` is correct
3. Check browser console for CORS errors
4. Ensure the API server allows requests from your domain

## Contributing

When contributing to the Admin UI:

1. Follow the existing code style
2. Add TypeScript types for new features
3. Test both development and production builds
4. Update documentation as needed

## License

See the main project LICENSE file.
