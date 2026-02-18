# HITL (Human-In-The-Loop) - Complete Guide

**✅ HITL IS NOW WORKING - Bug fixed in `engine.py`**

See `HITL_GUIDE.md` for the fix details and production usage.

---

## 1. What Happens When HITL is Enabled

### Workflow Execution Flow

```
START
  ↓
PLANNER (select next skill)
  ↓
EXECUTOR (run the skill) ← Skill EXECUTES here
  ↓
ROUTE_POST_EXEC (check routing)
  ├─ If hitl_enabled=True → HUMAN_REVIEW (PAUSE) ⏸️
  ├─ If executor="rest" → AWAIT_CALLBACK (PAUSE) ⏸️
  └─ Otherwise → PLANNER (continue)
```

### ⚠️ IMPORTANT: HITL Timing
**HITL pauses AFTER skill execution, not before!**

This means:
- ✅ Skill has already run
- ✅ Outputs are in `data_store`
- ✅ Human reviews/edits the RESULTS
- ✅ Then workflow continues to next skill

### When Workflow Pauses at HITL

1. **Graph Execution**:
   - Skill executes normally
   - `route_post_exec()` checks `skill_meta.hitl_enabled`
   - Routes to `"human_review"` node
   - `interrupt_before=["human_review"]` causes pause

2. **Checkpoint Saved**:
   - Full state saved to PostgreSQL `checkpoints` table
   - `next=["human_review"]` indicates resume point
   
3. **Status Updated**:
   - `run_metadata.status` changes to `"paused"`
   - API returns `{"status": "paused"}`

4. **UI Notification**:
   - Real-time WebSocket/Pusher event sent
   - Admin UI shows "Paused for Human Review" banner
   - "Approve & Continue" button appears

## 2. Resume Technique

### API Endpoint: `/approve/{thread_id}`

```python
POST /approve/{thread_id}
Body: {
  "updated_data": {  // Optional: edited data_store
    "field1": "new value",
    "field2": 123
  }
}
```

### Resume Process

```python
# Step 1: Human optionally edits data
if updated_data:
    await app.aupdate_state(config, {"data_store": updated_data})

# Step 2: Resume execution from checkpoint
async for _ in app.astream(None, config):
    pass  # Workflow continues from human_review node

# Step 3: Check where it ended up
state = await app.aget_state(config)
if not state.next:
    # Completed successfully
    status = "completed"
elif "human_review" in state.next:
    # Hit another HITL skill
    status = "paused"
```

### What Happens on Resume

1. **State Loaded**: Checkpoint retrieved from PostgreSQL
2. **Execution Continues**: Graph resumes from `human_review` node
3. **Routes to Planner**: `human_review → planner` edge
4. **Next Skill Selected**: Planner picks next skill based on updated data
5. **Workflow Continues**: Executes until completion or next pause

## 3. Data Storage During Pause

### Primary: PostgreSQL Checkpoints

**Table**: `checkpoints`

```sql
CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    checkpoint JSONB NOT NULL,  -- Full state here
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

**Checkpoint JSONB Structure**:
```json
{
  "id": "1ef2...",
  "channel_values": {
    "data_store": {
      "candidate_name": "John Doe",
      "email": "john@example.com",
      "verification_status": "pending",
      ...
    },
    "active_skill": "EmailVerifier",
    "history": [
      "Skill ProfileRetriever executed.",
      "Skill EmailVerifier executed."
    ],
    "execution_sequence": ["ProfileRetriever", "EmailVerifier"],
    "workspace_id": "ws-123"
  },
  "next": ["human_review"],  // Resume point
  "metadata": {...}
}
```

### Secondary: Redis Buffer (Optional, 30min TTL)

**Purpose**: Performance optimization for hot checkpoints
**Keys**: `checkpoint:{thread_id}:*`
**TTL**: 1800 seconds (30 minutes)
**Fallback**: Auto-loads from PostgreSQL if expired

### Tertiary: In-Memory Cache

**Purpose**: Ultra-fast access within same process
**Lifetime**: Process lifetime only
**Cleared**: After PostgreSQL flush

### Run Metadata (Separate Table)

**Table**: `run_metadata`

```sql
CREATE TABLE run_metadata (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT UNIQUE NOT NULL,
    run_name TEXT,
    sop TEXT NOT NULL,  -- Original instructions
    initial_data JSONB NOT NULL,  -- Starting data
    llm_model TEXT,
    status TEXT DEFAULT 'running',  -- 'running', 'paused', 'completed', 'error'
    completed_at TIMESTAMP,
    error_message TEXT,
    failed_skill TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    workspace_id TEXT
);
```

**Purpose**: Stores run configuration separate from checkpoints
**Why**: Enables rerun with same inputs, status tracking, history

## 4. Why HITL Might Not Work

### Issue #1: Skills Not Reloaded ⚠️ MOST LIKELY CAUSE

**Problem**: 
- You update `hitl_enabled` in database
- But skill registry in memory is stale
- `route_post_exec()` reads from old in-memory registry

**Solution**:
```bash
# Option A: Call reload endpoint (HOT RELOAD)
POST /admin/skills/reload
Headers: Authorization: Bearer <token>

# Option B: Restart the API server
# (skills load from DB at startup)
```

### Issue #2: Wrong Workspace

**Problem**: Skill belongs to different workspace than run

**Check**:
```sql
SELECT name, hitl_enabled, workspace_id, enabled 
FROM dynamic_skills 
WHERE name = 'YourSkillName';
```

**Solution**: Ensure skill workspace matches run workspace

### Issue #3: Skill Disabled

**Problem**: `enabled = FALSE` in database

**Check**: Same SQL query above, look at `enabled` column

**Solution**: Re-enable skill via UI or:
```sql
UPDATE dynamic_skills 
SET enabled = TRUE 
WHERE name = 'YourSkillName';
```

Then call `/admin/skills/reload`

### Issue #4: Checking Wrong Logs

**Problem**: Looking at old logs, not current run

**Solution**: Filter logs by `thread_id`, look for:
```
[ROUTER] HITL enabled for SkillName. Redirecting to HUMAN_REVIEW.
[API] Workflow paused at human_review (HITL) for thread=...
```

## 5. Testing HITL

### Step 1: Enable HITL on a Skill

```bash
# Via UI
1. Go to Skills → [Skill Name] → Edit
2. Check "Enable HITL after this skill"
3. Save

# Or via API
PUT /admin/skills/{skill_id}
Body: {"hitl_enabled": true}
```

### Step 2: Reload Skills (CRITICAL!)

```bash
POST /admin/skills/reload
```

### Step 3: Start a Run

```bash
POST /start
Body: {
  "sop": "Verify candidate John Doe",
  "initial_data": {"candidate_name": "John Doe"},
  "workspace_id": "your-workspace-id"
}
```

### Step 4: Monitor Execution

```bash
GET /status/{thread_id}

# Expected response when HITL triggers:
{
  "is_paused": true,
  "is_human_review": true,
  "next_node": ["human_review"],
  "active_skill": "YourSkillName",
  "data": {...}  // Current data_store
}
```

### Step 5: Review & Approve

```bash
# View in UI
http://localhost:3000/admin/{thread_id}

# Or approve via API
POST /approve/{thread_id}
Body: {
  "updated_data": {  // Optional edits
    "verification_status": "approved"
  }
}
```

### Step 6: Verify Continuation

Workflow should resume and continue to next skill or completion.

## 6. Debugging Commands

### Check if HITL is Enabled in DB
```sql
SELECT 
    name, 
    hitl_enabled, 
    enabled, 
    workspace_id,
    executor
FROM dynamic_skills
WHERE name = 'YourSkillName';
```

### Check Run Status
```sql
SELECT 
    thread_id,
    run_name,
    status,
    error_message,
    created_at
FROM run_metadata
WHERE thread_id = 'your-thread-id';
```

### Check Checkpoint State
```sql
SELECT 
    thread_id,
    checkpoint_id,
    checkpoint->'next' as next_nodes,
    checkpoint->'channel_values'->'active_skill' as active_skill,
    metadata
FROM checkpoints
WHERE thread_id = 'your-thread-id'
ORDER BY checkpoint_id DESC
LIMIT 1;
```

### Check Logs
```sql
SELECT 
    timestamp,
    level,
    message
FROM logs
WHERE thread_id = 'your-thread-id'
ORDER BY timestamp DESC
LIMIT 50;
```

## 7. Quick Fix Checklist

- [ ] 1. Verify `hitl_enabled = TRUE` in database
- [ ] 2. Verify `enabled = TRUE` in database
- [ ] 3. Call `/admin/skills/reload` endpoint (⭐ MOST IMPORTANT)
- [ ] 4. Start new run (don't reuse old thread_id)
- [ ] 5. Check logs for "[ROUTER] HITL enabled"
- [ ] 6. Check status endpoint shows `is_human_review: true`
- [ ] 7. Verify UI shows "Paused for Human Review"

## 8. Architecture Summary

```
┌─────────────────────────────────────────────────────┐
│  Skill Metadata (in-memory registry)                │
│  ┌──────────────────────────────────────┐          │
│  │ name: "EmailVerifier"                 │          │
│  │ hitl_enabled: TRUE ← Read from here! │          │
│  │ executor: "llm"                       │          │
│  └──────────────────────────────────────┘          │
└─────────────────────────────────────────────────────┘
                        ↑
                        │ Loaded at startup
                        │ & on /admin/skills/reload
                        ↓
┌─────────────────────────────────────────────────────┐
│  PostgreSQL: dynamic_skills table                   │
│  ┌──────────────────────────────────────┐          │
│  │ name: "EmailVerifier"                 │          │
│  │ hitl_enabled: TRUE                    │          │
│  │ enabled: TRUE                         │          │
│  └──────────────────────────────────────┘          │
└─────────────────────────────────────────────────────┘

During Execution:
┌─────────────────────────────────────────────────────┐
│  LangGraph Workflow                                 │
│  1. PLANNER → 2. EXECUTOR → 3. ROUTE_POST_EXEC     │
│                                   │                  │
│                            Checks hitl_enabled      │
│                                   │                  │
│                         If True → HUMAN_REVIEW ⏸️   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Checkpoint Saved to PostgreSQL                     │
│  {                                                   │
│    "next": ["human_review"],                        │
│    "channel_values": {                              │
│      "data_store": {...},  ← Full state            │
│      "active_skill": "EmailVerifier"                │
│    }                                                 │
│  }                                                   │
└─────────────────────────────────────────────────────┘
                        ↓
                  Status: "paused"
                        ↓
              Human Reviews in UI
                        ↓
              POST /approve/{thread_id}
                        ↓
              Workflow Resumes
```

## 9. Pro Tips

1. **Always Reload After Editing**: Hit `/admin/skills/reload` after any skill changes
2. **Check Logs First**: Look for "[ROUTER] HITL enabled" message
3. **Use Status Endpoint**: `/status/{thread_id}` shows current pause state
4. **Edit Data Carefully**: Updated data must match expected schema
5. **Multiple HITLs**: Workflow can pause multiple times if multiple skills have HITL enabled
6. **Timeout**: No automatic timeout - runs stay paused until approved
7. **Persistence**: Checkpoints persist across server restarts

## 10. Common Patterns

### Pattern: Review Before Final Step
```
Skills: [DataCollection, DataValidation, FinalSubmission]
HITL on: DataValidation
Use case: Review validated data before submitting
```

### Pattern: Error Correction
```
Skills: [AutoVerify]
HITL on: AutoVerify
Use case: If verification fails, human can correct and retry
```

### Pattern: Multi-Stage Approval
```
Skills: [Draft, Review1, Review2, Publish]
HITL on: Review1, Review2
Use case: Multiple approval gates
```
