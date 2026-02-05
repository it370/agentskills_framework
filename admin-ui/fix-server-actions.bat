@echo off
REM Fix Next.js Server Action errors by cleaning cache and rebuilding

echo [FIX] Cleaning Next.js cache and build artifacts...
echo.

REM Remove .next directory
if exist ".next" (
    echo [FIX] Removing .next directory...
    rd /s /q ".next"
)

REM Remove node_modules/.cache
if exist "node_modules\.cache" (
    echo [FIX] Removing node_modules cache...
    rd /s /q "node_modules\.cache"
)

REM Remove turbo cache
if exist ".turbo" (
    echo [FIX] Removing .turbo directory...
    rd /s /q ".turbo"
)

echo.
echo [FIX] Cache cleaned successfully!
echo [FIX] Now run: npm run dev
echo.
pause
