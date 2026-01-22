# Testing Callback URL Feature with curl

## Prerequisites

1. Have the API server running on `http://localhost:8000`
2. Have an authentication token (login via `/auth/login`)
3. Have a webhook testing service URL (e.g., from webhook.site or requestbin.com)

## Step 1: Get a Webhook Testing URL

Visit https://webhook.site/ and copy your unique URL.
Example: `https://webhook.site/a1b2c3d4-e5f6-7890-abcd-ef1234567890`

## Step 2: Start a Workflow with Callback

Replace `YOUR_AUTH_TOKEN` and `YOUR_WEBHOOK_URL` with your values:

```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "thread_id": "test_callback_001",
    "sop": "Test workflow for callback feature demonstration",
    "initial_data": {
      "test_key": "test_value"
    },
    "callback_url": "YOUR_WEBHOOK_URL",
    "run_name": "Callback Test Run"
  }'
```

Example with real values:
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "thread_id": "test_callback_001",
    "sop": "Test workflow for callback feature demonstration",
    "initial_data": {
      "test_key": "test_value"
    },
    "callback_url": "https://webhook.site/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "run_name": "Callback Test Run"
  }'
```

## Step 3: Monitor the Workflow

Check the webhook.site page - when the workflow completes, you'll see a POST request with the run metadata.

## Expected Callback Payload

```json
{
  "thread_id": "test_callback_001",
  "status": "completed",
  "error_message": null,
  "run_name": "Callback Test Run",
  "created_at": "2026-01-22T10:30:00.123456Z",
  "llm_model": "gpt-4",
  "failed_skill": null,
  "completed_at": "2026-01-22T10:35:00.654321Z"
}
```

**Note:** The callback payload is minimal (8 fields only) for performance. If you need additional data like `sop`, `initial_data`, `workspace_id`, or `parent_thread_id`, query the full metadata endpoint:

```bash
curl -X GET http://localhost:8000/admin/runs/test_callback_001/metadata \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

## Step 4: Test Rerun with Different Callback

```bash
curl -X POST http://localhost:8000/rerun/test_callback_001 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "callback_url": "https://webhook.site/another-webhook-url"
  }'
```

## Notes

- The callback is invoked AFTER the run status is updated in the database
- The payload is **minimal** (8 fields only) for performance and reduced network overhead
- Query `/admin/runs/{thread_id}/metadata` if you need full run details (SOP, initial_data, etc.)
- Callbacks are non-blocking - failures don't affect workflow execution
- Check the run logs to see callback invocation messages
