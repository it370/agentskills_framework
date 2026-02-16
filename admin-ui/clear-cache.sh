#!/bin/bash

echo "======================================"
echo "Clearing ALL Next.js Caches"
echo "======================================"
echo ""

cd "$(dirname "$0")"

echo "[1/6] Stopping any running dev servers..."
echo "Press Ctrl+C in the terminal running 'npm run dev' if needed"
sleep 3
echo ""

echo "[2/6] Deleting .next folder..."
if [ -d ".next" ]; then
    rm -rf .next
    echo "    ✓ Deleted .next"
else
    echo "    - No .next folder found"
fi
echo ""

echo "[3/6] Deleting node_modules/.cache..."
if [ -d "node_modules/.cache" ]; then
    rm -rf node_modules/.cache
    echo "    ✓ Deleted node_modules/.cache"
else
    echo "    - No cache folder found"
fi
echo ""

echo "[4/6] Deleting .turbopack cache (if exists)..."
if [ -d ".turbopack" ]; then
    rm -rf .turbopack
    echo "    ✓ Deleted .turbopack"
else
    echo "    - No .turbopack folder found"
fi
echo ""

echo "[5/6] Deleting out folder (if exists)..."
if [ -d "out" ]; then
    rm -rf out
    echo "    ✓ Deleted out folder"
else
    echo "    - No out folder found"
fi
echo ""

echo "[6/6] Clearing npm cache..."
npm cache clean --force
echo ""

echo "======================================"
echo "All caches cleared successfully!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Make sure dev server is stopped"
echo "  2. Run: npm run dev"
echo "  3. Hard refresh browser: Ctrl+Shift+R"
echo ""
