# Pub/Sub Configuration Guide

## Overview

The framework uses a unified pub/sub client that supports both **PostgreSQL NOTIFY/LISTEN** and **Redis Pub/Sub** for broadcasting checkpoint events to the admin UI.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  engine.py                                              │
│  ↓                                                       │
│  checkpoint saved → pubsub_client.publish()            │
└─────────────────────────────────────────────────────────┘
                          ↓
                   [Pub/Sub Backend]
                   Redis or PostgreSQL
                          ↓
┌─────────────────────────────────────────────────────────┐
│  api/main.py                                            │
│  ↓                                                       │
│  pubsub_client.listen() → WebSocket broadcast          │
└─────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Choose backend: 'redis' or 'postgres' (default: postgres)
PUBSUB_BACKEND=postgres

# PostgreSQL (used if PUBSUB_BACKEND=postgres)
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Redis Option 1: Connection String (used if PUBSUB_BACKEND=redis)
REDIS_URL=redis://localhost:6379/0

# Redis Option 2: Separate Parameters (used if PUBSUB_BACKEND=redis and REDIS_URL not set)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_USERNAME=myuser     # Optional
REDIS_PASSWORD=mypass     # Optional
```

**Note:** For Redis, if `REDIS_URL` is set, it takes precedence over separate parameters.

## Usage Examples

### Option 1: PostgreSQL (Default)

**Pros:**
- No extra service needed
- Simple setup
- Good for low-medium volume

**Cons:**
- Requires polling (100ms interval)
- Not as efficient as Redis

**Setup:**
```bash
# .env file
PUBSUB_BACKEND=postgres
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
```

That's it! Restart your API and it will use PostgreSQL.

### Option 2: Redis

**Pros:**
- No polling, true push model
- More efficient
- Better for high volume
- Purpose-built for pub/sub

**Cons:**
- Requires Redis server

**Setup:**

1. **Install Redis:**
```bash
# Windows (using Chocolatey)
choco install redis

# Or use Docker
docker run -d -p 6379:6379 redis:alpine

# Or use a managed service (AWS ElastiCache, Redis Cloud, etc.)
```

2. **Install Python Redis package:**
```bash
conda activate clearstar
pip install redis
```

3. **Configure environment (Option 1 - Connection String):**
```bash
# .env file
PUBSUB_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
```

**Or configure environment (Option 2 - Separate Parameters):**
```bash
# .env file
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# REDIS_USERNAME=myuser  # Optional, if Redis requires auth
# REDIS_PASSWORD=mypass  # Optional, if Redis requires auth
```

4. **Restart your API**

The framework will automatically use Redis instead of PostgreSQL.

## Automatic Fallback

If you set `PUBSUB_BACKEND=redis` but the `redis` package is not installed, the system automatically falls back to PostgreSQL:

```
[PubSub] Redis not available, falling back to PostgreSQL
```

## Programmatic Usage

### Publishing Events

```python
from pubsub_client import get_default_client

# Get the client (singleton)
pubsub = get_default_client()

# Publish a message
pubsub.publish('run_events', {
    'thread_id': 'abc123',
    'checkpoint_id': 'xyz789',
    'status': 'running'
})
```

### Listening for Events

```python
from pubsub_client import get_default_client
from threading import Event

stop_flag = Event()

def on_message(payload):
    print(f"Received: {payload}")

# Get the client
pubsub = get_default_client()

# Listen (blocking)
pubsub.listen('run_events', on_message, stop_flag)

# To stop:
stop_flag.set()
```

### Custom Client

```python
from pubsub_client import RedisPubSubClient, set_default_client

# Option 1: Create Redis client with connection string
redis_client = RedisPubSubClient(
    connection_string='redis://localhost:6379/0'
)

# Option 2: Create Redis client with separate parameters
redis_client = RedisPubSubClient(
    host='localhost',
    port=6379,
    db=0,
    username='myuser',  # Optional
    password='mypass'   # Optional
)

# Set as default
set_default_client(redis_client)
```

## Performance Comparison

| Metric | PostgreSQL | Redis |
|--------|-----------|-------|
| **Latency** | ~100-200ms | ~1-10ms |
| **CPU Usage** | Low-Medium | Low |
| **Throughput** | 100s/sec | 10,000s/sec |
| **Polling** | Yes (100ms) | No (push) |
| **Memory** | Minimal | Minimal |

## Monitoring

### Check Backend in Use

Look for startup logs:
```
[PubSub] Listening on PostgreSQL channel: run_events
# or
[PubSub] Listening on Redis channel: run_events
```

### Test Publishing

```python
# In Python shell
from pubsub_client import get_default_client

pubsub = get_default_client()
pubsub.publish('run_events', {'test': 'message'})
```

Check your admin UI WebSocket console - you should see the event.

## Troubleshooting

### PostgreSQL: "Connection refused"

- Check `DATABASE_URL` is correct
- Ensure PostgreSQL is running
- Verify network connectivity

### Redis: "Connection refused"

- Check Redis is running: `redis-cli ping` (should return `PONG`)
- Verify `REDIS_URL` is correct
- Check firewall settings

### No events received

1. Check listener is running:
   ```
   [PubSub] Listening on <backend> channel: run_events
   ```

2. Check publisher is working (look for errors in engine logs)

3. Verify WebSocket connection in browser console

### High CPU usage

If using PostgreSQL and seeing high CPU:
- This is expected with tight polling loop
- Consider switching to Redis
- Or accept 100ms latency with current implementation

## Migration

### From PostgreSQL to Redis

1. Install Redis and `redis` Python package
2. Update `.env` with one of these options:
   
   **Option A (Connection String):**
   ```bash
   PUBSUB_BACKEND=redis
   REDIS_URL=redis://localhost:6379/0
   ```
   
   **Option B (Separate Parameters):**
   ```bash
   PUBSUB_BACKEND=redis
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   REDIS_USERNAME=myuser  # Optional
   REDIS_PASSWORD=mypass  # Optional
   ```

3. Restart API

No code changes needed! The abstraction layer handles everything.

### From Redis to PostgreSQL

1. Update `.env`: `PUBSUB_BACKEND=postgres`
2. Restart API

## Best Practices

1. **Use Redis in production** if you have it available
2. **PostgreSQL is fine** for dev/small deployments
3. **Monitor CPU usage** if using PostgreSQL
4. **Set appropriate timeouts** in production
5. **Handle reconnections** gracefully (client auto-reconnects on errors)

## Security

### PostgreSQL
- Uses existing database credentials
- Same security as your database

### Redis
- Use `redis://user:pass@host:port/db` for authentication (connection string)
- Or use separate `REDIS_USERNAME` and `REDIS_PASSWORD` env vars
- Enable TLS: `rediss://host:port/db` (connection string)
- Restrict network access via firewall

## Summary

| Use Case | Recommended Backend | Configuration |
|----------|-------------------|---------------|
| **Development** | PostgreSQL (simple) | Just use DATABASE_URL |
| **Small production** | PostgreSQL (good enough) | Just use DATABASE_URL |
| **High volume** | Redis | Use REDIS_HOST/PORT/PASSWORD |
| **Already have Redis** | Redis | Use REDIS_HOST/PORT/PASSWORD |
| **Minimize dependencies** | PostgreSQL | Just use DATABASE_URL |
| **Cloud Redis (managed)** | Redis | Use REDIS_URL or separate params |

## Examples

### Example 1: Local Development (PostgreSQL)
```bash
# .env
PUBSUB_BACKEND=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agentskills
```

### Example 2: Local Redis (No Auth)
```bash
# .env
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Example 3: Production Redis with Authentication
```bash
# .env
PUBSUB_BACKEND=redis
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_DB=0
REDIS_USERNAME=app_user
REDIS_PASSWORD=secure_password_here
```

### Example 4: AWS ElastiCache Redis
```bash
# .env
PUBSUB_BACKEND=redis
REDIS_HOST=my-cluster.abcdef.ng.0001.use1.cache.amazonaws.com
REDIS_PORT=6379
REDIS_DB=0
# ElastiCache doesn't use username/password by default, uses VPC security
```

### Example 5: Redis Cloud (Connection String)
```bash
# .env
PUBSUB_BACKEND=redis
REDIS_URL=redis://default:password@redis-12345.c1.us-east-1-2.ec2.cloud.redislabs.com:12345
```

### Example 6: Docker Compose Redis
```yaml
# docker-compose.yml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    command: redis-server --requirepass mypassword

# .env
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=mypassword
```

