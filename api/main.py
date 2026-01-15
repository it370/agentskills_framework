import os
import asyncio
import threading
import json
from typing import Any, Dict, Optional
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from psycopg import Connection as SyncConnection
from env_loader import load_env_once

# Load environment variables before importing other modules
load_env_once(Path(__file__).resolve().parent.parent)

from engine import AgentState, app, _deep_merge_dict, checkpointer, _safe_serialize, _get_env_value, _AsyncPostgresSaver
import log_stream
from log_stream import publish_log, emit_log, set_log_context, get_thread_logs
from .mock_api import router as mock_router
from .auth_api import router as auth_router
from admin_events import broadcast_run_event
from services.connection_pool import get_pool_stats, health_check as check_pool_health, get_postgres_pool
from services.auth_middleware import AuthenticatedUser, OptionalUser, AdminUser

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

api = FastAPI(title="Agentic SOP Orchestrator")

# CORS: allow all for dev, or specific origins from env
if "*" in ALLOWED_ORIGINS:
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,  # Cannot be True with allow_origins=["*"]
        expose_headers=["*"],
    )
else:
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
        expose_headers=["*"],
    )

# Authentication endpoints
api.include_router(auth_router)

# Mock endpoints for hardcoded data (sandbox/testing)
api.include_router(mock_router)

class StartRequest(BaseModel):
    thread_id: str
    sop: str
    initial_data: Dict[str, Any]
    run_name: Optional[str] = None  # Human-friendly name (optional)
    ack_key: Optional[str] = None  # Unique key for ACK handshake

@api.post("/start")
async def start_process(req: StartRequest, current_user: AuthenticatedUser):
    """
    Start a workflow with ACK handshake for instant UI feedback.
    
    Flow:
    1. Send ACK via Pusher immediately (UI can redirect)
    2. Save metadata and create checkpoint
    3. Run workflow (sends progress updates via Pusher)
    4. Return response
    """
    # Use run_name if provided, otherwise default to thread_id
    run_name = req.run_name if req.run_name and req.run_name.strip() else req.thread_id
    
    # STEP 1: Save metadata FIRST (so it's available when UI fetches after redirect)
    await _save_run_metadata(req.thread_id, req.sop, req.initial_data, run_name=run_name, user_id=current_user.id)
    # STEP 2: Send ACK via Pusher (UI will receive and redirect)
    if req.ack_key:
        # await publish_log(f"[API] Sending ACK for thread={req.thread_id} with ack_key={req.ack_key}", req.thread_id)
        # ticker.settick("Sent ACK")
        await broadcast_run_event({
            "type": "ack",
            "ack_key": req.ack_key,
            "thread_id": req.thread_id,
            "run_name": run_name,
            "status": "accepted"
        })
        # await publish_log(f"[API] ACK sent successfully", req.thread_id)
        # ticker.settick("Published ACK")
    else:
        await publish_log(f"[API] No ack_key provided, skipping ACK", req.thread_id)
    
    # STEP 3: Create initial checkpoint
    config = {"configurable": {"thread_id": req.thread_id}}
    initial_state = {
        "layman_sop": req.sop,
        "data_store": req.initial_data,
        "history": ["Process Started"],
        "thread_id": req.thread_id,
    }
    
    await app.aupdate_state(config, initial_state)
    
    # STEP 4: Broadcast workflow started event
    await broadcast_run_event({
        "type": "run_started",
        "thread_id": req.thread_id,
        "run_name": run_name,
        "user": current_user.username
    })
    
    # Set log context
    set_log_context(req.thread_id)
    
    # STEP 5: Log start
    emit_log(f"[API] Start requested for thread={req.thread_id} by user={current_user.username}", req.thread_id)
    # STEP 6: Run workflow (will send progress updates via Pusher)
    asyncio.create_task(_run_workflow(initial_state, config))
    # STEP 7: Return response
    return {"status": "started", "thread_id": req.thread_id, "run_name": run_name}


async def _save_run_metadata(thread_id: str, sop: str, initial_data: Dict[str, Any], parent_thread_id: Optional[str] = None, run_name: Optional[str] = None, user_id: Optional[int] = None):
    """Save run metadata to database using connection pool for rerun functionality."""
    try:
        pool = get_postgres_pool()
    except RuntimeError:
        emit_log("[API] Postgres pool not available, skipping run metadata save")
        return
    
    # Default run_name to thread_id if not provided
    if not run_name or not run_name.strip():
        run_name = thread_id
    
    def _save_sync():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                # Check if parent thread exists and get its rerun count
                rerun_count = 0
                if parent_thread_id:
                    cur.execute(
                        "SELECT rerun_count FROM run_metadata WHERE thread_id = %s",
                        (parent_thread_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        rerun_count = row[0] + 1
                
                # Insert run metadata
                cur.execute("""
                    INSERT INTO run_metadata (thread_id, run_name, sop, initial_data, parent_thread_id, rerun_count, status, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, 'running', %s)
                    ON CONFLICT (thread_id) DO UPDATE
                    SET run_name = EXCLUDED.run_name,
                        sop = EXCLUDED.sop,
                        initial_data = EXCLUDED.initial_data,
                        parent_thread_id = EXCLUDED.parent_thread_id,
                        rerun_count = EXCLUDED.rerun_count,
                        user_id = EXCLUDED.user_id
                """, (thread_id, run_name, sop, json.dumps(initial_data), parent_thread_id, rerun_count, user_id))
            conn.commit()
        finally:
            pool.putconn(conn)
    
    try:
        await asyncio.to_thread(_save_sync)
        # emit_log(f"[API] Saved run metadata for thread={thread_id}, name={run_name}, user_id={user_id}")
    except Exception as e:
        emit_log(f"[API] Failed to save run metadata: {e}")


async def _check_run_ownership(thread_id: str, user_id: int):
    """
    Check if user owns a run
    
    Raises HTTPException if not owner or run not found
    """
    db_uri = _get_env_value("DATABASE_URL", "")
    if not db_uri:
        return  # Skip check if DB not configured
    
    def _check_sync():
        import psycopg
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id::text FROM run_metadata WHERE thread_id = %s
                """, (thread_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return row[0]
    
    try:
        owner_id = await asyncio.to_thread(_check_sync)
        if owner_id is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if owner_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this run")
    except HTTPException:
        raise
    except Exception as e:
        emit_log(f"[API] Failed to check run ownership: {e}")


async def _update_run_status(thread_id: str, status: str, error_message: Optional[str] = None, failed_skill: Optional[str] = None):
    """Update the run status in run_metadata table and flush Redis checkpoints if completed."""
    db_uri = _get_env_value("DATABASE_URL", "")
    if not db_uri:
        return

    def _update_sync():
        import psycopg
        from datetime import datetime
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE run_metadata
                    SET status = %s,
                        error_message = %s,
                        failed_skill = %s,
                        completed_at = %s
                    WHERE thread_id = %s
                """, (status, error_message, failed_skill, datetime.utcnow(), thread_id))

    try:
        await asyncio.to_thread(_update_sync)
        emit_log(f"[API] Updated run status to '{status}' for thread={thread_id}")
    except Exception as e:
        emit_log(f"[API] Failed to update run status: {e}")
        return
    
    # ALWAYS broadcast status update, regardless of checkpoint flush
    try:
        await broadcast_run_event({
            "thread_id": thread_id,
            "status": status,
            "type": "status_updated",
        })
    except Exception as e:
        emit_log(f"[API] Failed to broadcast status update: {e}")
    
    # Flush Redis checkpoints to PostgreSQL on completion/error (non-blocking)
    if status in ["completed", "error"]:
        try:
            from services.checkpoint_buffer import RedisCheckpointBuffer
            buffer = RedisCheckpointBuffer()
            success = await buffer.flush_to_postgres(thread_id, db_uri)
            if success:
                emit_log(f"[API] Flushed checkpoints to PostgreSQL for {thread_id}")
            await buffer.close()
        except Exception as e:
            emit_log(f"[API] Error flushing checkpoints for {thread_id}: {e}")


async def _get_run_metadata(thread_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve run metadata from database."""
    db_uri = _get_env_value("DATABASE_URL", "")
    if not db_uri:
        return None
    
    def _get_sync():
        import psycopg
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT thread_id, run_name, sop, initial_data, created_at, parent_thread_id, rerun_count, metadata,
                           status, error_message, failed_skill, completed_at
                    FROM run_metadata
                    WHERE thread_id = %s
                """, (thread_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "thread_id": row[0],
                        "run_name": row[1] or row[0],  # Default to thread_id if run_name is None
                        "sop": row[2],
                        "initial_data": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "parent_thread_id": row[5],
                        "rerun_count": row[6],
                        "metadata": row[7],
                        "status": row[8],
                        "error_message": row[9],
                        "failed_skill": row[10],
                        "completed_at": row[11].isoformat() if row[11] else None
                    }
                return None
    
    try:
        return await asyncio.to_thread(_get_sync)
    except Exception as e:
        emit_log(f"[API] Failed to get run metadata: {e}")
        return None


async def _run_workflow(initial_state: Dict[str, Any], config: Dict[str, Any]):
    """Run workflow in background without blocking the start endpoint."""
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    
    # Set the thread context for all logs in this workflow
    set_log_context(thread_id)
    
    try:
        await app.ainvoke(initial_state, config)
        
        # Check the actual state after workflow execution
        state = await app.aget_state(config)
        next_nodes = state.next or []
        data_store = state.values.get("data_store", {})
        
        # Check if workflow failed
        if data_store.get("_status") == "failed":
            error_msg = data_store.get("_error", "Unknown error")
            failed_skill = data_store.get("_failed_skill")
            await _update_run_status(thread_id, "error", error_msg, failed_skill)
            await publish_log(f"[API] Workflow failed for thread={thread_id}", thread_id)
        # Determine if truly completed or paused at an interrupt
        elif not next_nodes or (len(next_nodes) == 1 and next_nodes[0] == "__end__"):
            await _update_run_status(thread_id, "completed")
            await publish_log(f"[API] Workflow completed for thread={thread_id}", thread_id)
        elif "human_review" in next_nodes:
            await _update_run_status(thread_id, "paused")
            await publish_log(f"[API] Workflow paused at human_review (HITL) for thread={thread_id}", thread_id)
        elif "await_callback" in next_nodes:
            await _update_run_status(thread_id, "paused")
            await publish_log(f"[API] Workflow paused awaiting callback for thread={thread_id}", thread_id)
        else:
            await publish_log(f"[API] Workflow paused at {next_nodes} for thread={thread_id}", thread_id)
            
    except Exception as exc:
        # Log the error
        await publish_log(f"[API] Workflow error for thread={thread_id}: {exc}", thread_id)
        
        # Update run status
        await _update_run_status(thread_id, "error", str(exc))
        
        # Update state to mark as failed and force workflow to END
        try:
            current_state = await app.aget_state(config)
            history = list(current_state.values.get("history", []))
            history.append(f"WORKFLOW FAILED: {exc}")
            
            # Update state with error information and set active_skill to END
            await app.aupdate_state(config, {
                "active_skill": "END",
                "history": history,
                "data_store": {
                    **current_state.values.get("data_store", {}),
                    "_error": str(exc),
                    "_status": "failed"
                }
            })
            
            await publish_log(f"[API] Workflow marked as failed and stopped for thread={thread_id}", thread_id)
        except Exception as update_exc:
            emit_log(f"[API] Failed to update workflow state after error: {update_exc}")

@api.get("/status/{thread_id}")
async def get_status(thread_id: str, current_user: AuthenticatedUser):
    config = {"configurable": {"thread_id": thread_id}}
    
    # Check if user owns this run
    await _check_run_ownership(thread_id, current_user.id)
    
    state = await app.aget_state(config)
    next_nodes = state.next or []
    is_human_review = "human_review" in next_nodes
    is_waiting_callback = "await_callback" in next_nodes
    
    # Check for error/failed status
    data_store = state.values.get("data_store", {})
    status = data_store.get("_status")
    error = data_store.get("_error")
    failed_skill = data_store.get("_failed_skill")
    
    return {
        "is_paused": len(next_nodes) > 0,
        "is_human_review": is_human_review,
        "is_waiting_callback": is_waiting_callback,
        "next_node": next_nodes,
        "active_skill": state.values.get("active_skill"),
        "data": data_store,
        "history": state.values.get("history"),
        "status": status,
        "error": error,
        "failed_skill": failed_skill
    }

@api.post("/approve/{thread_id}")
async def approve_step(
    thread_id: str, current_user: AuthenticatedUser, updated_data: Optional[Dict[str, Any]] = Body(None)
):
    config = {"configurable": {"thread_id": thread_id}}
    
    # Check if user owns this run
    await _check_run_ownership(thread_id, current_user.id)
    
    # Update status to 'running' when resuming from HITL pause
    await _update_run_status(thread_id, "running")
    
    # If the human edited data, update the state first
    if updated_data:
        await app.aupdate_state(config, {"data_store": updated_data})
        await publish_log(f"[API] Human updated data for thread={thread_id} by user={current_user.username}", thread_id)
    
    await publish_log(f"[API] Human approval received; resuming thread={thread_id} by user={current_user.username}", thread_id)
    
    # Resume the graph
    await app.ainvoke(None, config)
    
    # Check the state after resuming
    state = await app.aget_state(config)
    next_nodes = state.next or []
    
    # Update status based on where workflow ended up
    if not next_nodes or (len(next_nodes) == 1 and next_nodes[0] == "__end__"):
        await publish_log(f"[API] Workflow completed after approval for thread={thread_id}", thread_id)
        # Check if it failed or completed successfully
        data_store = state.values.get("data_store", {})
        if data_store.get("_status") == "failed":
            await _update_run_status(
                thread_id, 
                "error", 
                data_store.get("_error", "Workflow failed"),
                data_store.get("_failed_skill")
            )
        else:
            await _update_run_status(thread_id, "completed")
    elif "human_review" in next_nodes:
        await publish_log(f"[API] Workflow paused again at human_review for thread={thread_id}", thread_id)
        await _update_run_status(thread_id, "paused")
    elif "await_callback" in next_nodes:
        await publish_log(f"[API] Workflow paused awaiting callback for thread={thread_id}", thread_id)
        await _update_run_status(thread_id, "paused")
    else:
        await publish_log(f"[API] Workflow resumed and paused at {next_nodes} for thread={thread_id}", thread_id)
    
    return {"status": "resumed"}

class CallbackPayload(BaseModel):
    thread_id: str
    skill: str
    data: Dict[str, Any]
    error: Optional[str] = None


def _serialize_checkpoint_tuple(cp_tuple):
    """Convert a CheckpointTuple into a JSON-serializable dict."""
    return {
        "config": cp_tuple.config,
        "checkpoint": cp_tuple.checkpoint,
        "metadata": cp_tuple.metadata,
        "parent_config": cp_tuple.parent_config,
        "pending_writes": cp_tuple.pending_writes,
    }


@api.get("/admin/runs")
async def list_runs(current_user: AuthenticatedUser, limit: int = 50):
    """List workflow runs with computed status from database view."""
    # Try to use the database view for better performance
    db_uri = _get_env_value("DATABASE_URL", "")
    
    # Use database view if DATABASE_URL is available (works with both direct PostgreSQL and buffered modes)
    if db_uri:
        # Use database view with pre-computed status
        try:
            import psycopg
            
            def _fetch_from_view():
                with psycopg.connect(db_uri, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        # Filter by user_id unless admin
                        if current_user.is_admin:
                            cur.execute("""
                                SELECT 
                                    thread_id,
                                    checkpoint_id,
                                    checkpoint_ns,
                                    run_name,
                                    active_skill,
                                    history_count,
                                    status,
                                    sop_preview,
                                    created_at,
                                    updated_at,
                                    checkpoint,
                                    metadata,
                                    error_message,
                                    failed_skill
                                FROM run_list_view
                                ORDER BY created_at DESC NULLS LAST
                                LIMIT %s
                            """, (limit,))
                        else:
                            # For non-admin, query run_metadata directly to ensure user ownership
                            # Then join with view to get checkpoint data
                            cur.execute("""
                                SELECT 
                                    r.thread_id,
                                    r.checkpoint_id,
                                    r.checkpoint_ns,
                                    r.run_name,
                                    r.active_skill,
                                    r.history_count,
                                    r.status,
                                    r.sop_preview,
                                    r.created_at,
                                    r.updated_at,
                                    r.checkpoint,
                                    r.metadata,
                                    r.error_message,
                                    r.failed_skill
                                FROM run_metadata m
                                INNER JOIN run_list_view r ON m.thread_id = r.thread_id
                                WHERE m.user_id = %s
                                ORDER BY r.created_at DESC NULLS LAST
                                LIMIT %s
                            """, (current_user.id, limit))
                        
                        rows = cur.fetchall()
                        
                        return [
                            {
                                "thread_id": row[0],
                                "checkpoint_id": row[1],
                                "checkpoint_ns": row[2],
                                "run_name": row[3],
                                "active_skill": row[4],
                                "history_count": row[5],
                                "status": row[6],
                                "sop_preview": row[7],
                                "created_at": row[8].isoformat() if row[8] else None,
                                "updated_at": row[9].isoformat() if row[9] else None,
                                "checkpoint": row[10],
                                "metadata": row[11],
                                "error_message": row[12],
                                "failed_skill": row[13],
                            }
                            for row in rows
                        ]
            
            runs = await asyncio.to_thread(_fetch_from_view)
            return {"runs": runs}
            
        except Exception as e:
            emit_log(f"[ADMIN] Failed to fetch from view, falling back to checkpointer: {e}")
    
    # Fallback to original checkpointer method
    cp = checkpointer
    runs = []
    try:
        if hasattr(cp, "alist"):
            async for tup in cp.alist(None, limit=limit):
                runs.append(_serialize_checkpoint_tuple(tup))
        else:
            for tup in cp.list(None, limit=limit):  # type: ignore[attr-defined]
                runs.append(_serialize_checkpoint_tuple(tup))
    except NotImplementedError:
        pass
    return {"runs": runs}



@api.get("/admin/runs/{thread_id}")
async def run_detail(thread_id: str, current_user: AuthenticatedUser):
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id)
    
    cp = checkpointer
    config = {"configurable": {"thread_id": thread_id}}
    cp_tuple = None
    try:
        if hasattr(cp, "aget_tuple"):
            cp_tuple = await cp.aget_tuple(config)  # type: ignore[attr-defined]
    except NotImplementedError:
        cp_tuple = None
    if cp_tuple is None and hasattr(cp, "get_tuple"):
        cp_tuple = cp.get_tuple(config)  # type: ignore[attr-defined]
    if cp_tuple is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize_checkpoint_tuple(cp_tuple)


@api.get("/admin/runs/{thread_id}/logs")
async def get_logs(thread_id: str, current_user: AuthenticatedUser, limit: int = 1000):
    """Retrieve historical logs for a specific thread."""
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id)
    
    logs = await get_thread_logs(thread_id, limit)
    return {"logs": logs, "count": len(logs)}


@api.get("/admin/runs/{thread_id}/metadata")
async def get_run_metadata_endpoint(thread_id: str, current_user: AuthenticatedUser):
    """Get run metadata for a specific thread."""
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id)
    
    metadata = await _get_run_metadata(thread_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Run metadata not found")
    return metadata


class RerunRequest(BaseModel):
    ack_key: Optional[str] = None  # Unique key for ACK handshake

@api.post("/rerun/{thread_id}")
async def rerun_workflow(thread_id: str, current_user: AuthenticatedUser, req: RerunRequest = Body(default=RerunRequest())):
    """
    Rerun a workflow with ACK handshake for instant UI feedback.
    
    Flow:
    1. Send ACK via Pusher immediately (UI can redirect)
    2. Save metadata and create checkpoint
    3. Run workflow (sends progress updates via Pusher)
    4. Return response
    """
    import uuid
    import re
    
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id)
    
    # Get the original run metadata
    metadata = await _get_run_metadata(thread_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Original run not found")
    
    # Generate new thread ID with fresh GUID
    new_thread_id = f"thread_{uuid.uuid4()}"
    
    # Generate new run name based on original
    original_run_name = metadata.get('run_name', thread_id)
    base_run_name = re.sub(r'\s*\(Rerun #\d+\)\s*$', '', original_run_name).strip()
    new_run_name = f"{base_run_name} (Rerun #{metadata['rerun_count'] + 1})"
    
    # STEP 1: Save metadata FIRST (so it's available when UI fetches after redirect)
    await _save_run_metadata(
        new_thread_id,
        metadata["sop"],
        metadata["initial_data"],
        parent_thread_id=thread_id,
        run_name=new_run_name,
        user_id=current_user.id
    )
    
    # STEP 2: Send ACK via Pusher (UI will receive and redirect)
    if req.ack_key:
        await broadcast_run_event({
            "type": "ack",
            "ack_key": req.ack_key,
            "thread_id": new_thread_id,
            "run_name": new_run_name,
            "parent_thread_id": thread_id,
            "status": "accepted"
        })
    else:
        # Legacy: Send ACK without ack_key for backward compatibility
        await broadcast_run_event({
            "type": "ack",
            "thread_id": new_thread_id,
            "run_name": new_run_name,
            "parent_thread_id": thread_id,
            "status": "accepted"
        })
    
    # STEP 3: Create initial checkpoint
    config = {"configurable": {"thread_id": new_thread_id}}
    initial_state = {
        "layman_sop": metadata["sop"],
        "data_store": metadata["initial_data"],
        "history": [f"Process Started (Rerun from {base_run_name})"],
        "thread_id": new_thread_id,
    }
    await app.aupdate_state(config, initial_state)
    
    # STEP 4: Broadcast workflow started event
    await broadcast_run_event({
        "type": "run_started",
        "thread_id": new_thread_id,
        "run_name": new_run_name,
        "parent_thread_id": thread_id,
        "user": current_user.username
    })
    
    # Set log context
    set_log_context(new_thread_id)
    
    # STEP 5: Log start
    await publish_log(f"[API] Rerun requested from thread={thread_id} -> new thread={new_thread_id} by user={current_user.username}", new_thread_id)
    
    # STEP 6: Run workflow (will send progress updates via Pusher)
    asyncio.create_task(_run_workflow(initial_state, config))
    
    # STEP 7: Return response
    return {
        "status": "started",
        "thread_id": new_thread_id,
        "run_name": new_run_name,
        "parent_thread_id": thread_id,
        "rerun_count": metadata["rerun_count"] + 1
    }


@api.post("/callback")
async def rest_callback(req: CallbackPayload):
    config = {"configurable": {"thread_id": req.thread_id}}
    state = await app.aget_state(config)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown thread_id")

    current_values = state.values or {}
    data_store = current_values.get("data_store", {}) or {}
    history = list(current_values.get("history") or [])
    
    # Check if this callback has already been processed
    callback_marker = f"Executed {req.skill} (REST callback)"
    if callback_marker in history:
        await publish_log(f"[CALLBACK] Duplicate callback ignored for thread={req.thread_id}, skill={req.skill}")
        return {"status": "duplicate_ignored"}

    await publish_log(f"[CALLBACK] Received results for thread={req.thread_id}, skill={req.skill}", req.thread_id)

    merged = _deep_merge_dict(data_store, req.data)
    # Clear pending REST marker if present
    if "_rest_pending" in merged:
        pending = set(merged.get("_rest_pending") or [])
        pending.discard(req.skill)
        if pending:
            merged["_rest_pending"] = list(pending)
        else:
            merged.pop("_rest_pending", None)

    history.append(callback_marker)
    if req.error:
        history.append(f"Error from {req.skill}: {req.error}")

    # Update state with merged data and history
    # Don't set active_skill here - let the workflow resume naturally
    await app.aupdate_state(config, {
        "data_store": merged,
        "history": history,
    })

    # Resume the workflow - it will continue from await_callback node
    await app.ainvoke(None, config)
    await publish_log(f"[CALLBACK] Applied results and resumed thread={req.thread_id}", req.thread_id)
    return {"status": "resumed"}


# --- Demo REST endpoint to showcase callback-based execution ---
class DemoRestRequest(BaseModel):
    skill: str
    thread_id: str
    callback_url: str
    inputs: Dict[str, Any]
    expected_outputs: list[str] = []
    sop: str


@api.post("/demo/rest-task")
async def demo_rest_task(req: DemoRestRequest):
    """
    Simulates a long-running partner API. Acknowledges immediately, then after
    ~10 seconds POSTs to the provided callback_url with mock results.
    
    Note: The durable _rest_pending mechanism in the checkpointed state prevents
    duplicate execution at the orchestrator level. This endpoint trusts that
    the orchestrator won't send duplicate requests for the same skill+thread.
    """
    await publish_log(f"[DEMO REST] Received request for skill={req.skill}, thread={req.thread_id}", req.thread_id)

    async def _delayed_callback():
        await asyncio.sleep(10)
        payload = {
            "thread_id": req.thread_id,
            "skill": req.skill,
            "data": {
                "mock_result": "completed by demo endpoint",
                "echoed_inputs": req.inputs,
                "sop_seen": req.sop,
            },
        }
        try:
            # Log BEFORE sending so it appears in correct chronological order
            await publish_log(f"[DEMO REST] Sending callback for thread={req.thread_id}")
            async with httpx.AsyncClient() as client:
                await client.post(req.callback_url, json=payload)
            emit_log(f"[DEMO REST] Callback sent for thread={req.thread_id}", req.thread_id)
            await publish_log(f"[DEMO REST] Callback completed for thread={req.thread_id}")
        except Exception as exc:
            await publish_log(f"[DEMO REST] Callback failed for thread={req.thread_id}: {exc}")

    asyncio.create_task(_delayed_callback())
    return {"status": "accepted", "will_callback_in": "10s"}


@api.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        - status: "healthy" or "degraded"
        - checks: Individual health checks for services
    """
    try:
        # Check connection pools
        pools_healthy = check_pool_health()
        
        # Get pool statistics
        pool_stats = get_pool_stats()
        
        # Check broadcaster status
        try:
            from services.websocket import get_broadcaster_status
            broadcaster_status = get_broadcaster_status()
            broadcaster_available = broadcaster_status.get('primary_available', False)
        except Exception:
            broadcaster_available = False
        
        # Determine overall status
        status = "healthy" if (pools_healthy and broadcaster_available) else "degraded"
        
        return {
            "status": status,
            "timestamp": None,  # Will be set on client
            "checks": {
                "postgres": pool_stats.get("postgres_healthy", False),
                "mongodb": pool_stats.get("mongo_healthy", False),
                "broadcaster": broadcaster_available,
            },
            "details": pool_stats
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")




@api.get("/admin/broadcaster-status")
async def broadcaster_status():
    """
    Get real-time broadcaster status and statistics.
    
    Returns information about Pusher/Ably broadcaster availability, message counts, etc.
    """
    try:
        from services.websocket import get_broadcaster_status
        return get_broadcaster_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get broadcaster status: {str(e)}")


@api.get("/admin/pool-stats")
async def pool_statistics_endpoint():
    """
    Get detailed connection pool statistics for monitoring.
    
    Returns connection pool usage and health metrics.
    """
    try:
        stats = get_pool_stats()
        
        # Add computed metrics
        if "postgres_size" in stats and "postgres_available" in stats:
            stats["postgres_in_use"] = stats["postgres_size"] - stats["postgres_available"]
            if stats["postgres_size"] > 0:
                stats["postgres_utilization"] = (stats["postgres_in_use"] / stats["postgres_size"]) * 100
        
        return {
            "status": "success",
            "pool_stats": stats,
            "recommendations": _get_pool_recommendations(stats)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pool stats: {str(e)}")


def _get_pool_recommendations(stats: Dict[str, Any]) -> list[str]:
    """Generate recommendations based on pool statistics."""
    recommendations = []
    
    # Check Postgres pool utilization
    if "postgres_utilization" in stats:
        utilization = stats["postgres_utilization"]
        if utilization > 90:
            recommendations.append(
                "CRITICAL: Postgres pool utilization above 90%. "
                "Consider increasing POSTGRES_POOL_MAX_SIZE environment variable."
            )
        elif utilization > 75:
            recommendations.append(
                "WARNING: Postgres pool utilization above 75%. "
                "Monitor for potential connection exhaustion."
            )
    
    # Check waiting clients
    if stats.get("postgres_waiting", 0) > 0:
        recommendations.append(
            f"WARNING: {stats['postgres_waiting']} clients waiting for Postgres connections. "
            "This may cause performance issues."
        )
    
    # Check health
    if not stats.get("postgres_healthy", False):
        recommendations.append("CRITICAL: Postgres connection pool is unhealthy.")
    
    if not stats.get("mongo_healthy", False):
        recommendations.append("WARNING: MongoDB connection is unhealthy.")
    
    if not recommendations:
        recommendations.append("All systems operating normally.")
    
    return recommendations


# Import skill management endpoints
from api.skills_api import *

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000)