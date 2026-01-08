# Services Directory

This directory contains modular, self-contained services used by the application.

## Structure

Each service should be organized in its own subdirectory with:
```
services/
├── __init__.py
├── <service_name>/
│   ├── __init__.py           # Public API exports
│   ├── <implementation>.py   # Core implementation
│   ├── CONFIGURATION.md      # Configuration guide (if applicable)
│   ├── README.md             # Service overview
│   └── test_<name>.py        # Tests/examples (if applicable)
```

## Available Services

### Pub/Sub (`services/pubsub/`)

Event broadcasting service with support for Redis and PostgreSQL backends.

**Key Files:**
- `client.py` - Main implementation
- `CONFIGURATION.md` - Complete configuration guide
- `IMPLEMENTATION.md` - Architecture and implementation details
- `REDIS_CONFIGURATION.md` - Redis-specific configuration
- `test_client.py` - Test and example script

**Usage:**
```python
from services.pubsub import get_default_client

# Publish events
pubsub = get_default_client()
pubsub.publish('channel_name', {'data': 'value'})

# Listen for events
pubsub.listen('channel_name', callback_function, stop_flag)
```

**Configuration:**
```bash
# PostgreSQL (default)
PUBSUB_BACKEND=postgres
DATABASE_URL=postgresql://...

# Redis
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=secret
```

See [services/pubsub/CONFIGURATION.md](pubsub/CONFIGURATION.md) for details.

## Adding New Services

When adding a new modular feature, follow this pattern:

1. **Create service directory:**
   ```bash
   mkdir services/my_service
   ```

2. **Create `__init__.py` with public API:**
   ```python
   """
   My Service - Short description
   """
   from .implementation import MyClass, my_function
   
   __all__ = ['MyClass', 'my_function']
   ```

3. **Implement in separate files:**
   - Keep implementation details in `implementation.py` or similar
   - Use descriptive names for modules

4. **Add documentation:**
   - `README.md` - Overview and quick start
   - `CONFIGURATION.md` - Configuration options (if needed)
   - Examples in docstrings or separate files

5. **Make it testable:**
   - Include test file or examples
   - Use `test_<name>.py` naming convention

6. **Import from project code:**
   ```python
   from services.my_service import MyClass
   ```

## Design Principles

1. **Self-contained** - Each service should be independent
2. **Well-documented** - README and configuration docs
3. **Testable** - Include tests or examples
4. **Clean API** - Export only public interfaces via `__init__.py`
5. **Modular** - Easy to add, remove, or replace
6. **Configurable** - Use environment variables for configuration

## Examples of Future Services

Potential services that could be added:

- `services/cache/` - Redis/Memcached caching layer
- `services/logging/` - Structured logging service
- `services/metrics/` - Metrics collection and reporting
- `services/notifications/` - Email/SMS/Slack notifications
- `services/storage/` - File storage abstraction (S3, local, etc.)
- `services/auth/` - Authentication and authorization
- `services/queue/` - Task queue management
- `services/search/` - Search indexing and querying

## Benefits of Services Pattern

- ✅ **Organized** - Clear structure for modular features
- ✅ **Reusable** - Services can be shared across projects
- ✅ **Testable** - Isolated testing per service
- ✅ **Maintainable** - Easy to find and update code
- ✅ **Scalable** - Add new services without cluttering root
- ✅ **Documented** - Each service has its own docs

