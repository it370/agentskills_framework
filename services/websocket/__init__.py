"""
Real-time broadcasting via Server-Sent Events (SSE).

All real-time communication goes through SSE:
- Logs:         GET /api/runs/{thread_id}/logs/stream  or  GET /api/logs/stream
- Admin events: GET /api/admin-events/stream
"""
from .sse_broadcast import (
    broadcast_log_sse as broadcast_log,
    broadcast_admin_sse as broadcast_admin_event,
    get_sse_status as get_broadcaster_status,
    stream_logs_sse,
    stream_admin_sse,
)

__all__ = [
    "broadcast_log",
    "broadcast_admin_event",
    "get_broadcaster_status",
    "stream_logs_sse",
    "stream_admin_sse",
]
