@echo off
echo ======================================
echo Clearing ALL Next.js Caches
echo ======================================
echo.

cd /d "%~dp0"

echo [1/6] Stopping any running dev servers...
echo Press Ctrl+C in the terminal running 'npm run dev' if needed
timeout /t 3 /nobreak >nul
echo.

echo [2/6] Deleting .next folder...
if exist .next (
    rmdir /s /q .next
    echo     ✓ Deleted .next
) else (
    echo     - No .next folder found
)
echo.

echo [3/6] Deleting node_modules/.cache...
if exist node_modules\.cache (
    rmdir /s /q node_modules\.cache
    echo     ✓ Deleted node_modules/.cache
) else (
    echo     - No cache folder found
)
echo.

echo [4/6] Deleting .turbopack cache (if exists)...
if exist .turbopack (
    rmdir /s /q .turbopack
    echo     ✓ Deleted .turbopack
) else (
    echo     - No .turbopack folder found
)
echo.

echo [5/6] Deleting out folder (if exists)...
if exist out (
    rmdir /s /q out
    echo     ✓ Deleted out folder
) else (
    echo     - No out folder found
)
echo.

echo [6/6] Clearing npm cache...
call npm cache clean --force
echo.

echo ======================================
echo All caches cleared successfully!
echo ======================================
echo.
echo Next steps:
echo   1. Make sure dev server is stopped
echo   2. Run: npm run dev
echo   3. Hard refresh browser: Ctrl+Shift+R
echo.
pause
