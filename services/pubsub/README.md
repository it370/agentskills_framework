# Pub/Sub Service

Event broadcasting service with unified interface for Redis and PostgreSQL backends.

## Quick Start

### Import
```python
from services.pubsub import get_default_client
```

### Publish Events
```python
pubsub = get_default_client()
pubsub.publish('run_events', {
    'thread_id': 'abc123',
    'status': 'running'
})
```

### Listen for Events
```python
from threading import Event

stop_flag = Event()

def on_message(payload):
    print(f"Received: {payload}")

pubsub.listen('run_events', on_message, stop_flag)
```

## Configuration

### PostgreSQL (Default)
```bash
PUBSUB_BACKEND=postgres
DATABASE_URL=postgresql://user:pass@localhost:5432/db
```

### Redis
```bash
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=secret
```

## Documentation

- **[CONFIGURATION.md](CONFIGURATION.md)** - Complete configuration guide
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Architecture and implementation details
- **[REDIS_CONFIGURATION.md](REDIS_CONFIGURATION.md)** - Redis-specific setup

## Testing

```bash
# From project root
python services/pubsub/test_client.py both

# Or as module
python -m services.pubsub.test_client both
```

## Features

- ✅ Unified API for both backends
- ✅ Automatic backend selection
- ✅ Graceful fallback (Redis → PostgreSQL)
- ✅ Configurable via environment variables
- ✅ Efficient polling for PostgreSQL
- ✅ True push model for Redis
- ✅ Thread-safe operations
- ✅ Easy to test and mock

## API Reference

### `create_pubsub_client(backend=None, connection_string=None)`
Factory function to create a pub/sub client.

### `get_default_client()`
Get or create the default singleton client.

### `set_default_client(client)`
Set a custom default client (useful for testing).

### `PubSubClient.publish(channel, message)`
Publish a message to a channel. Returns `True` on success.

### `PubSubClient.listen(channel, callback, stop_flag)`
Listen for messages (blocking). Calls `callback(payload)` for each message.

### `PubSubClient.close()`
Close connections and cleanup resources.

## Performance

| Backend | Latency | Throughput | CPU | Polling |
|---------|---------|------------|-----|---------|
| PostgreSQL | ~100ms | 100s/sec | Low | Yes (100ms) |
| Redis | ~10ms | 10,000s/sec | Very Low | No |

## Used By

- `engine.py` - Publishes checkpoint save events
- `api/main.py` - Listens for events and broadcasts to WebSocket clients

