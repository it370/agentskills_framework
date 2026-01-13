# SSE Migration - Quick Setup Guide

## ✅ What Was Done

The system now supports **both WebSocket and SSE** (Server-Sent Events). You can switch between them using a simple environment variable.

---

## 🚀 How to Use SSE (Current Configuration)

### Step 1: Environment Already Set
Your `.env` file is already configured to use SSE:

```env
NEXT_PUBLIC_CONNECTION_METHOD=sse
```

### Step 2: Restart Services

**Restart Python Backend:**
```bash
# Stop current process (Ctrl+C in terminal)
# Then start again
python main.py
```

**Restart Next.js (if needed):**
```bash
# Stop (Ctrl+C)
npm run dev
```

### Step 3: Test
1. Open browser and go to your admin UI
2. Open DevTools Console (F12)
3. Look for:
   ```
   [API] Using SSE for logs
   [API] Using SSE for admin events
   [SSE] Logs connection opened
   ```

4. Start a workflow run
5. Go to Logs page
6. You should see logs streaming! ✅

---

## 🔄 Switch Back to WebSocket (If Needed)

Just change one line in `.env`:

```env
# Use WebSocket instead
NEXT_PUBLIC_CONNECTION_METHOD=websocket
```

Then restart Next.js.

---

## 📊 What You'll See

### SSE Mode (Current):
```
Browser Console:
[API] Using SSE for logs
[SSE] Logs connection opened
```

### WebSocket Mode:
```
Browser Console:
[API] Using WebSocket for logs
[API] Logs websocket connected
```

---

## 🐛 Troubleshooting

### No logs appearing?

**Check 1: Python Backend**
Make sure you see these new endpoints when starting:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Check 2: Browser Console**
Should see:
```
[API] Using SSE for logs
[SSE] Logs connection opened
```

If you see WebSocket errors instead, the env variable didn't reload.

**Check 3: Network Tab**
1. Open DevTools → Network tab
2. Filter by "sse"
3. Should see:
   - `sse/logs` - Status: 200, Type: text/event-stream
   - `sse/admin` - Status: 200, Type: text/event-stream

---

## ✅ Benefits of SSE

- ✅ Works through IIS without any configuration
- ✅ Uses regular HTTPS (no special WebSocket setup needed)
- ✅ Auto-reconnection built into browser
- ✅ Same speed as WebSocket for your use case
- ✅ More reliable with reverse proxies

---

## 📝 Technical Details

**Frontend Changes:**
- `src/lib/api.ts` - Added `useSSE()` check
- Both `connectAdminEvents()` and `connectLogs()` now route to SSE or WebSocket based on env

**Backend Changes:**
- `api/main.py` - Added `/sse/logs` and `/sse/admin` endpoints
- `log_stream.py` - Added SSE client support
- `admin_events.py` - Added SSE client support

**Configuration:**
- `.env` - Added `NEXT_PUBLIC_CONNECTION_METHOD`

---

## 🎯 Summary

**Current State:**
- ✅ SSE is enabled by default
- ✅ WebSocket code is still there (can switch anytime)
- ✅ No code removal, just added options

**To Test:**
1. Start Python backend
2. Start Next.js
3. Run a workflow
4. Check logs page - should stream! 🚀

**If SSE doesn't work:**
- Switch back to `websocket` mode in `.env`
- Or check console for errors

---

Need help? Check browser console for error messages!
