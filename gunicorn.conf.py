"""
Gunicorn configuration for AgentSkills Framework (Production)

This configuration uses Uvicorn workers for ASGI support (FastAPI).
"""
import os
import multiprocessing
from pathlib import Path

# Load environment variables
from env_loader import load_env_once
load_env_once(Path(__file__).resolve().parent)

# Server socket
bind = f"{os.getenv('REST_API_HOST', '0.0.0.0')}:{os.getenv('REST_API_PORT', '8000')}"

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'uvicorn.workers.UvicornWorker'
worker_connections = 1000
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', 10000))
max_requests_jitter = 1000

# Timeout
timeout = int(os.getenv('GUNICORN_TIMEOUT', 120))
keepalive = 5
graceful_timeout = 30

# SSL/TLS Configuration
ssl_keyfile = os.getenv('SSL_KEYFILE')
ssl_certfile = os.getenv('SSL_CERTFILE')
if ssl_keyfile and ssl_certfile:
    keyfile = ssl_keyfile
    certfile = ssl_certfile

# Logging
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # - means stdout
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')    # - means stderr
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'agentskills_framework'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Preload app for better memory usage
# NOTE: Set to False if you have issues with class variables/singletons not being
# properly initialized in worker processes (e.g., AuthContext)
preload_app = False

# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("[GUNICORN] Starting AgentSkills Framework...")

def when_ready(server):
    """Called just after the server is started."""
    protocol = "https" if (ssl_keyfile and ssl_certfile) else "http"
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AgentSkills Framework - Production Mode           ║
╠══════════════════════════════════════════════════════════════╣
║  Server:             Gunicorn + Uvicorn Workers             ║
║  Bind Address:       {bind:<44}║
║  Workers:            {workers:<44}║
║  SSL/TLS:            {'Enabled' if (ssl_keyfile and ssl_certfile) else 'Disabled':<44}║
║  Worker Class:       {worker_class:<44}║
╚══════════════════════════════════════════════════════════════╝
""")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("[GUNICORN] Shutting down...")
    try:
        from services.connection_pool import close_pools
        close_pools()
        print("[GUNICORN] Connection pools closed")
    except Exception as e:
        print(f"[GUNICORN] Warning: Failed to close connection pools: {e}")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    print(f"[GUNICORN] Worker {worker.pid} interrupted")

def worker_abort(worker):
    """Called when a worker receives the ABRT signal."""
    print(f"[GUNICORN] Worker {worker.pid} aborted")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"[GUNICORN] Worker spawned (pid: {worker.pid})")
    
    # CRITICAL: Reset and re-initialize auth context per worker
    # Class variables from master process may not carry over properly after fork
    try:
        from services.credentials import AuthContext
        
        # Reset the auth context to ensure clean state in worker
        AuthContext.reset()
        
        # Re-initialize for this worker
        auth = AuthContext.initialize_from_env()
        print(f"[WORKER {worker.pid}] Auth context initialized for user: {auth.get_current_user().user_id}")
    except Exception as e:
        print(f"[WORKER {worker.pid}] WARNING: Could not initialize auth context: {e}")
        print(f"[WORKER {worker.pid}] Credential-based skills may fail without user_context in inputs")
    
    print(f"[WORKER {worker.pid}] Real-time broadcast: SSE (Server-Sent Events)")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def pre_exec(server):
    """Called just before a new master process is forked."""
    print("[GUNICORN] Preparing for new master process...")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    print(f"[GUNICORN] Worker exited (pid: {worker.pid})")
