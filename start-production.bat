@echo off
REM Production startup script for AgentSkills Framework (Windows)
REM Uses Uvicorn ASGI server (same as python main.py)

cd /d "%~dp0"

@REM REM Activate conda environment
@REM echo [STARTUP] Activating conda environment: clearstar
@REM call conda activate clearstar || (
@REM     echo [ERROR] Failed to activate conda environment 'clearstar'
@REM     echo [ERROR] Make sure conda is installed and environment exists
@REM     pause
@REM     exit /b 1
@REM )

REM Set default values
if not defined REST_API_HOST set REST_API_HOST=0.0.0.0
if not defined REST_API_PORT set REST_API_PORT=8000

echo [STARTUP] Starting AgentSkills Framework (Production)...
echo [STARTUP] Server: Uvicorn ASGI
echo [STARTUP] Bind: %REST_API_HOST%:%REST_API_PORT%
echo.

REM Start production server using main.py (same as development)
python main.py
