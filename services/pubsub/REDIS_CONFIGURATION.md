# Redis Configuration Quick Reference

## Environment Variable Options

### Option 1: Connection String (Simple)
```bash
PUBSUB_BACKEND=redis
REDIS_URL=redis://[username:password@]host:port/db
```

**Examples:**
```bash
# No auth
REDIS_URL=redis://localhost:6379/0

# With password only
REDIS_URL=redis://:mypassword@localhost:6379/0

# With username and password
REDIS_URL=redis://myuser:mypassword@redis.example.com:6379/0

# With TLS
REDIS_URL=rediss://myuser:mypassword@redis.example.com:6380/0
```

### Option 2: Separate Parameters (Flexible)
```bash
PUBSUB_BACKEND=redis
REDIS_HOST=localhost        # Required
REDIS_PORT=6379             # Required (default: 6379)
REDIS_DB=0                  # Optional (default: 0)
REDIS_USERNAME=myuser       # Optional
REDIS_PASSWORD=mypass       # Optional
```

## When to Use Each Option

| Scenario | Recommended Option | Why |
|----------|-------------------|-----|
| **Local development** | Option 2 (separate) | Clearer, easier to modify |
| **Cloud managed Redis** | Option 1 (URL) | Cloud providers give you URLs |
| **Docker/K8s** | Option 2 (separate) | Easier to inject from secrets |
| **Multiple environments** | Option 2 (separate) | Easier to override per env |
| **Simple setup** | Option 1 (URL) | One variable to set |

## Priority

If **both** are set, `REDIS_URL` takes precedence over separate parameters.

## Common Configurations

### Local Redis (Docker)
```bash
# docker run -d -p 6379:6379 redis:alpine
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Local Redis with Password
```bash
# docker run -d -p 6379:6379 redis:alpine redis-server --requirepass mypassword
PUBSUB_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=mypassword
```

### AWS ElastiCache
```bash
PUBSUB_BACKEND=redis
REDIS_HOST=my-cluster.xxx.ng.0001.use1.cache.amazonaws.com
REDIS_PORT=6379
```

### Azure Cache for Redis
```bash
PUBSUB_BACKEND=redis
REDIS_HOST=mycache.redis.cache.windows.net
REDIS_PORT=6380
REDIS_PASSWORD=primary-key-here
# Note: Azure uses port 6380 with TLS by default
```

### Redis Cloud
```bash
# They provide a URL
PUBSUB_BACKEND=redis
REDIS_URL=redis://default:password@redis-12345.redislabs.com:12345
```

### Kubernetes Secret (Separate Params)
```yaml
# ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  PUBSUB_BACKEND: "redis"
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  REDIS_DB: "0"

# Secret
apiVersion: v1
kind: Secret
metadata:
  name: redis-credentials
type: Opaque
stringData:
  REDIS_USERNAME: "app_user"
  REDIS_PASSWORD: "secure_password"
```

## Testing Your Configuration

```bash
# Test Redis connection
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping
# Should return: PONG

# Test pub/sub
python test_pubsub.py both
```

## Migration from REDIS_URL to Separate Parameters

**Before:**
```bash
REDIS_URL=redis://myuser:mypass@redis.example.com:6379/0
```

**After:**
```bash
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_DB=0
REDIS_USERNAME=myuser
REDIS_PASSWORD=mypass
```

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** or secret management (Vault, AWS Secrets Manager, etc.)
3. **Enable TLS** in production (`rediss://` or configure separately)
4. **Use strong passwords** (at least 32 characters, random)
5. **Restrict network access** (VPC, security groups, firewall rules)
6. **Use username/password** if Redis version supports ACLs (6.0+)

## Troubleshooting

### "Connection refused"
- Check Redis is running: `redis-cli ping`
- Verify host and port are correct
- Check firewall/security groups

### "Authentication failed"
- Verify username/password are correct
- Check if Redis requires AUTH: `redis-cli CONFIG GET requirepass`

### "Wrong database"
- Redis has databases 0-15 by default
- Verify REDIS_DB is valid

### Using URL but getting connection errors
- Try separate parameters instead
- URL parsing might fail with special characters in password
- URL-encode special characters: `myp@ss` → `myp%40ss`

