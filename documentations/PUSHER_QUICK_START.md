# Pusher Setup - Quick Start

## 1. Get Pusher Credentials (5 minutes)

1. Go to [https://pusher.com](https://pusher.com)
2. Sign up / Log in
3. Click "Create app"
4. Choose:
   - **Name**: AgentSkills (or your preferred name)
   - **Cluster**: `ap2` (Asia Pacific) - choose closest to your users
   - **Tech stack**: Can skip this
5. Click "App Keys" tab
6. Copy these values:
   - `app_id`
   - `key`
   - `secret`
   - `cluster`

## 2. Configure Backend (2 minutes)

Edit `.env` file in project root:

```bash
# Add these lines
PUSHER_APP_ID=your_app_id_here
PUSHER_KEY=your_key_here
PUSHER_SECRET=your_secret_here
PUSHER_CLUSTER=ap2
```

Install Python dependency:

```bash
conda activate clearstar
pip install pusher
```

## 3. Configure Frontend (2 minutes)

Create/edit `admin-ui/.env.local`:

```bash
NEXT_PUBLIC_PUSHER_KEY=your_key_here
NEXT_PUBLIC_PUSHER_CLUSTER=ap2
NEXT_PUBLIC_USE_PUSHER=true
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

Install npm dependency:

```bash
cd admin-ui
npm install
```

## 4. Test It! (1 minute)

**Start backend:**
```bash
python main.py
```

Look for:
```
[PUSHER] Initialized successfully (cluster: ap2)
[MAIN] Real-time broadcast configured: pusher (available)
```

**Start frontend:**
```bash
cd admin-ui
npm run dev
```

**Open browser:**
1. Go to `http://localhost:3000/logs`
2. Open browser console (F12)
3. Look for: `[PUSHER] Logs connected`

**Trigger a workflow** and watch logs appear in real-time!

---

## Verify Setup

### ✅ Backend Check
```bash
curl http://localhost:8000/admin/broadcaster-status
```

Should show:
```json
{
  "primary_broadcaster": "pusher",
  "primary_available": true,
  ...
}
```

### ✅ Frontend Check
- Open logs page
- See "Streaming from Pusher Channels" in header
- See green "Connected" indicator

---

## Troubleshooting

**Backend not starting?**
- Check all 4 Pusher env vars are set in `.env`
- Run `pip install pusher`
- Restart terminal/IDE to reload env vars

**Frontend not connecting?**
- Check `NEXT_PUBLIC_PUSHER_KEY` in `admin-ui/.env.local`
- Run `npm install` in admin-ui folder
- Hard refresh browser (Ctrl+Shift+R)
- Check browser console for errors

**Still not working?**
- See full guide: `PUSHER_INTEGRATION_GUIDE.md`
- Check Pusher dashboard for errors
- Test with Pusher debug console

---

## Next Steps

- Set up usage alerts in Pusher dashboard
- Test with real workflows
- Read full integration guide for advanced features

**Setup time: ~10 minutes total** ⚡

**Free tier includes:**
- 200K messages/day (plenty for 100+ workflows/day)
- 100 concurrent connections
- All features included

Enjoy real-time updates without managing infrastructure! 🎉
