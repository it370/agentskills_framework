# Database Connection Pool Issue - Quick Fix

## Problem
Your PostgreSQL database is rejecting connections:
```
FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute
```

This means you've hit the database connection limit.

## Why This Happens

Your app uses TWO connection pools:
- Main pool: max_size=20
- Log pool: max_size=10
- **Total: 30 connections**

But your database likely allows only **20 connections** for non-superusers.

## Quick Fix (Do This Now)

1. **Stop Python backend** (Ctrl+C or kill process)
2. **Restart it:**
   ```bash
   python main.py
   ```

This releases all connections.

## Permanent Fix

Reduce connection pool sizes in `engine.py`:

**Current:**
```python
pool = ConnectionPool(conninfo=DB_URI, max_size=20, kwargs=connection_kwargs)
log_pool = ConnectionPool(conninfo=DB_URI, min_size=1, max_size=10)
```

**Change to:**
```python
pool = ConnectionPool(conninfo=DB_URI, max_size=10, kwargs=connection_kwargs)
log_pool = ConnectionPool(conninfo=DB_URI, min_size=1, max_size=5)
```

This limits total connections to 15 (well under database limit).

## Check Database Limits

Run this SQL to see your limits:
```sql
SHOW max_connections;
SELECT rolconnlimit FROM pg_roles WHERE rolname = 'your_username';
```

## Why SSE Appeared Broken

SSE **was actually working** (you saw 200 OK), but:
- Couldn't query database for run status → "pending"
- Couldn't fetch events from database → no messages
- Connection pool exhausted → everything stuck

Once you restart, SSE should work perfectly! ✅

## After Restart

1. Open `sse-test.html`
2. Click "Connect" - should see connection message
3. Start a workflow - should see events streaming
4. Runs page should show correct status

The issue wasn't SSE, it was database connection exhaustion!
