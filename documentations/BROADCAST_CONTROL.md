# Broadcast Flag Control Guide

## What is the Broadcast Flag?

The `broadcast` flag controls whether workflow execution logs (200+ messages per run) are sent in real-time to Pusher/AppSync for live UI updates. Admin events (5-10 status messages like run_started, run_completed) always broadcast regardless of this flag because they're lightweight and essential for UI state management.

By default, `broadcast: false` is used for headless/programmatic executions to save on API costs and network bandwidth. When running workflows from the Admin UI, `broadcast: true` is automatically set to provide real-time log streaming. This design gives you cost savings for background jobs while maintaining a great user experience for interactive runs.

Logs are always saved to the database regardless of the broadcast setting, so you never lose any data. The flag only controls whether logs are streamed in real-time to connected clients.

## How to Enable/Disable Broadcasting

### Enable Broadcasting (Interactive UI Runs)

To get real-time log streaming in the UI, include `broadcast: true` in your API request:

```bash
# Start a new workflow with live logs
curl -X POST http://localhost:8000/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "interactive_run_001",
    "sop": "Process order",
    "initial_data": {"order_id": "12345"},
    "broadcast": true,
    "ack_key": "ui_session_123"
  }'

# Rerun a workflow with live logs
curl -X POST http://localhost:8000/rerun/thread_xxx \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ack_key": "rerun_key_456",
    "broadcast": true
  }'
```

**Result:** You'll see all 200+ log messages streaming in real-time as the workflow executes, plus admin events for status updates.

### Disable Broadcasting (Headless/Background Jobs)

For programmatic executions where you don't need live updates, simply omit the `broadcast` parameter or set it to `false`:

```bash
# Headless execution (default behavior)
curl -X POST http://localhost:8000/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "batch_job_001",
    "sop": "Process batch",
    "initial_data": {"batch_id": "67890"},
    "callback_url": "https://myapp.com/webhook"
  }'
```

**Result:** The workflow executes normally with all logs saved to the database, but no real-time broadcasts are sent. You'll still receive admin events (run_started, run_completed) so the UI can show basic status, but the heavy log stream is skipped. Use the `callback_url` to get notified when the workflow completes.

## Cost Savings

### Per Run Comparison
- **With `broadcast: false`** (headless): ~5 API calls (admin events only) = $0.00025 per run
- **With `broadcast: true`** (interactive): ~205 API calls (5 admin + 200 logs) = $0.01025 per run
- **Savings per headless run:** 97.5% reduction in broadcast costs

### At Scale (1000 runs/day)
- **All headless (broadcast: false):** 5,000 broadcasts/day = ~$7.50/month
- **All interactive (broadcast: true):** 205,000 broadcasts/day = ~$307.50/month
- **Hybrid workload (70% headless, 30% interactive):** 65,000 broadcasts/day = ~$97.50/month with $210/month savings

## Admin UI Behavior

The Admin UI automatically includes `broadcast: true` when starting or rerunning workflows from the web interface. This is configured in:
- `admin-ui/src/app/runs/new/page.tsx` - New run form
- `admin-ui/src/lib/api.ts` - Rerun function

You don't need to do anything special in the UI—live log streaming just works. The optimization only affects programmatic API calls where you explicitly control the broadcast setting.
