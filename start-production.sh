#!/bin/bash
#
# Production startup script for AgentSkills Framework
# Uses Gunicorn with Uvicorn workers for optimal performance
#

# Exit on error
set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "[STARTUP] Loading environment from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Activate conda environment if specified
if [ ! -z "$CONDA_ENV" ]; then
    echo "[STARTUP] Activating conda environment: $CONDA_ENV"
    eval "$(conda shell.bash hook)"
    conda activate "$CONDA_ENV"
fi

# Set default values
export REST_API_HOST="${REST_API_HOST:-0.0.0.0}"
export REST_API_PORT="${REST_API_PORT:-8000}"
export GUNICORN_WORKERS="${GUNICORN_WORKERS:-$(($(nproc) * 2 + 1))}"
export GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
export GUNICORN_LOG_LEVEL="${GUNICORN_LOG_LEVEL:-info}"

echo "[STARTUP] Starting AgentSkills Framework..."
echo "[STARTUP] Workers: $GUNICORN_WORKERS"
echo "[STARTUP] Bind: $REST_API_HOST:$REST_API_PORT"
echo "[STARTUP] Timeout: $GUNICORN_TIMEOUT seconds"

# Recover buffered checkpoints before starting
echo "[STARTUP] Checking for buffered checkpoints..."
python -c "
import asyncio
from services.checkpoint_buffer import recover_buffered_checkpoints
from engine import _get_env_value

db_uri = _get_env_value('DATABASE_URL', '')
if db_uri:
    asyncio.run(recover_buffered_checkpoints(db_uri))
    print('[STARTUP] Checkpoint recovery complete')
else:
    print('[STARTUP] No DATABASE_URL configured, skipping checkpoint recovery')
" 2>/dev/null || echo "[STARTUP] Checkpoint recovery skipped (module not available)"

# Start Gunicorn with Uvicorn workers
exec gunicorn \
    --config gunicorn.conf.py \
    api:api
