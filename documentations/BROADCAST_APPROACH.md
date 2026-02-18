# Broadcast Approach

All real-time communication uses **Server-Sent Events (SSE)** served directly by the FastAPI backend. No third-party cloud broadcaster (Pusher, AppSync, etc.) is required.

---

## What gets broadcast

1. **Logs** – Each line of workflow output, streamed as it is produced.
2. **Admin events** – run started, run completed, checkpoint notifications, HITL ack, cancellation, etc.

---

## SSE streams

### Logs

Each log line is:

1. **Written to Redis** (`logs:queue:{thread_id}`) for durability (or to an in-process buffer if Redis is unavailable).
2. **Pushed immediately** to in-memory SSE subscriber queues (no delay).

Two endpoints are available:

| Stream | Endpoint | Description |
|--------|----------|-------------|
| Global | `GET /api/logs/stream` | All logs from all threads |
| Per-thread | `GET /api/runs/{thread_id}/logs/stream` | Logs for one specific thread |

**No historical replay on connect** – clients receive only new log lines after connecting. Historical logs are fetched separately from the database via `GET /admin/runs/{thread_id}/logs`.

**Persistence** – No per-line DB write. Logs are batch-flushed from Redis to the `thread_logs` table:
- **End of run**: When a run reaches `completed`, `error`, `cancelled`, or `paused` status.
- **App restart**: Any remaining Redis log keys are drained on startup (crash recovery).
- **Redis unavailable**: An in-process buffer is used instead; logs are still batch-flushed at end-of-run.

### Admin events

One global SSE stream:

```
GET /api/admin-events/stream
```

All admin events are broadcast to every subscriber. Clients filter by `thread_id` or event `type` as needed.

---

## Redis role

Redis is used only as a short-lived durability buffer for logs (same Redis instance as the checkpoint buffer). If Redis is unavailable, logs flow through SSE in real time and are batched in-process until flushed to the database at run end.

---

## Summary

| Aspect | Detail |
|--------|--------|
| Log transport | Redis buffer → immediate SSE push (global or per-thread) |
| Admin transport | In-memory → immediate SSE push (global) |
| Persistence | Batch flush from Redis to DB at end of run and on restart |
| Historical logs on connect | No – fetch via REST (`/admin/runs/{thread_id}/logs`) |
| External service required | None |
