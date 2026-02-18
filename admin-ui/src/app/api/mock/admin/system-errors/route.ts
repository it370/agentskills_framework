// Mock API route for testing System Errors UI locally
// Remove this file when using real backend

import { NextRequest, NextResponse } from 'next/server';

const MOCK_ERRORS = [
  {
    id: 1,
    error_type: "checkpoint_flush_error",
    severity: "critical",
    thread_id: "thread_7091aafd-9c60-422c-bbdf-840102276865",
    error_message: "invalid input syntax for type json - Token 'NaN' is invalid",
    stack_trace: `Traceback (most recent call last):
  File "C:\\projects\\agentskills_framework\\services\\checkpoint_buffer.py", line 234, in flush_to_postgres
    await asyncio.to_thread(_write_sync)
  File "C:\\Users\\Administrator\\miniconda3\\envs\\kudos\\Lib\\asyncio\\threads.py", line 25, in to_thread
    return await loop.run_in_executor(None, func_call)
psycopg.errors.InvalidTextRepresentation: invalid input syntax for type json
DETAIL:  Token "NaN" is invalid.
CONTEXT:  JSON data, line 1: ...487228814582)))"}], "neighbor_bounding_box": [NaN...`,
    error_context: {
      checkpoint_count: 42,
      error_type: "InvalidTextRepresentation",
      db_uri_configured: true
    },
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 2,
    error_type: "checkpoint_flush_error",
    severity: "warning",
    thread_id: "thread_abc123-def456-789012",
    error_message: "Checkpoint flush returned False - possible network timeout",
    stack_trace: null,
    error_context: {
      checkpoint_count: 15,
      db_uri_configured: true,
      status: "completed"
    },
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: 3,
    error_type: "checkpoint_flush_error",
    severity: "error",
    thread_id: null,
    error_message: "Database connection pool exhausted - unable to flush checkpoints",
    stack_trace: `Traceback (most recent call last):
  File "C:\\projects\\agentskills_framework\\services\\checkpoint_buffer.py", line 195, in flush_to_postgres
    with psycopg.connect(db_uri, autocommit=True) as conn:
ConnectionError: Could not connect to database: connection pool exhausted`,
    error_context: {
      checkpoint_count: 8,
      pool_size: 10,
      active_connections: 10
    },
    created_at: new Date(Date.now() - 300000).toISOString(),
  },
];

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const severity = searchParams.get('severity');
  const error_type = searchParams.get('error_type');
  
  let filtered = [...MOCK_ERRORS];
  
  if (severity) {
    filtered = filtered.filter(e => e.severity === severity);
  }
  if (error_type) {
    filtered = filtered.filter(e => e.error_type === error_type);
  }
  
  return NextResponse.json({
    status: "success",
    count: filtered.length,
    errors: filtered,
    filters: { error_type, severity, limit: 100 }
  });
}
