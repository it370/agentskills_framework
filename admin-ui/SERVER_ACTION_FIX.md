# Next.js Server Action Errors - Fix Guide

## Problem
The admin-ui application throws multiple console errors:
```
Error: Failed to find Server Action "x". This request might be from an older or newer deployment.
```

## Root Cause
This error occurs even when your app doesn't use Server Actions. It's caused by:
1. **Stale build cache** - The `.next` directory contains corrupted artifacts
2. **Hot reload issues** - Fast Refresh performing full reloads repeatedly
3. **Webpack cache mismatches** - Development server using outdated module references

## Solutions

### Quick Fix (Recommended)

1. **Stop the dev server** in Terminal 2:
   - Press `Ctrl+C` to stop `npm run dev`

2. **Run the cleanup script**:
   ```bash
   cd admin-ui
   .\fix-server-actions.bat
   ```

3. **Restart the dev server**:
   ```bash
   npm run dev
   ```

### Manual Fix

If the script doesn't work, manually:

1. Stop the dev server (`Ctrl+C`)
2. Delete cache directories:
   ```powershell
   cd admin-ui
   Remove-Item -Recurse -Force .next
   Remove-Item -Recurse -Force node_modules\.cache -ErrorAction SilentlyContinue
   Remove-Item -Recurse -Force .turbo -ErrorAction SilentlyContinue
   ```
3. Restart: `npm run dev`

### Nuclear Option

If errors persist after cleanup:

```powershell
# Stop dev server
# Then run:
Remove-Item -Recurse -Force node_modules
Remove-Item -Recurse -Force .next
npm install
npm run dev
```

## Configuration Changes Made

Updated `next.config.mjs` to:
- Configure server actions properly (even though not used)
- Improve development stability with `onDemandEntries`
- Reduce memory footprint during hot reload

## Prevention

To avoid this issue in the future:
1. **Avoid editing files while saving repeatedly** - Can corrupt hot reload
2. **Clear cache after package updates** - Run cleanup script after `npm install`
3. **Use production builds for testing** - `npm run build && npm start` doesn't have hot reload issues
4. **Restart dev server periodically** - Long-running dev servers accumulate cache issues

## When to Use Production Mode

For testing without hot reload issues:
```bash
npm run build
npm start
```

This creates a production build without Fast Refresh, eliminating server action lookup errors.

## Related Files
- `fix-server-actions.bat` - Automated cleanup script
- `next.config.mjs` - Updated configuration
- `.next/` - Build cache (deleted by fix)
- `node_modules/.cache/` - Module cache (deleted by fix)

## Testing After Fix

1. Navigate to `http://localhost:3000`
2. Open browser DevTools console
3. Navigate through pages (login, skills, admin, etc.)
4. Verify no "Failed to find Server Action" errors appear

If errors still appear, run the "Nuclear Option" fix.
