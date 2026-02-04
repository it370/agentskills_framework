@echo off
REM Production startup script for AgentSkills Framework (Windows)
REM Uses Waitress WSGI server (Windows-compatible)

cd /d "%~dp0"

REM Activate conda environment
echo [STARTUP] Activating conda environment: kudos
call conda activate kudos || (
    echo [ERROR] Failed to activate conda environment 'kudos'
    echo [ERROR] Make sure conda is installed and environment exists
    pause
    exit /b 1
)

REM Set default values
if not defined REST_API_HOST set REST_API_HOST=0.0.0.0
if not defined REST_API_PORT set REST_API_PORT=8000
if not defined WAITRESS_THREADS set WAITRESS_THREADS=5
if not defined WAITRESS_CHANNEL_TIMEOUT set WAITRESS_CHANNEL_TIMEOUT=120

echo [STARTUP] Starting AgentSkills Framework (Production)...
echo [STARTUP] Server: Waitress WSGI
echo [STARTUP] Threads: %WAITRESS_THREADS%
echo [STARTUP] Bind: %REST_API_HOST%:%REST_API_PORT%
echo [STARTUP] Timeout: %WAITRESS_CHANNEL_TIMEOUT% seconds
echo.

REM Start production server
python production_server.py
