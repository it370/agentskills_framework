import os
import asyncio
import threading
import json
from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime

import httpx
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from psycopg import Connection as SyncConnection
from env_loader import load_env_once

# Load environment variables before importing other modules
load_env_once(Path(__file__).resolve().parent.parent)

from engine import (
    AgentState,
    app,
    _deep_merge_dict,
    checkpointer,
    _safe_serialize,
    _get_env_value,
    _AsyncPostgresSaver,
    _resolve_global_llm_model,
)
import log_stream
from log_stream import publish_log, emit_log, set_log_context, get_thread_logs
from .mock_api import router as mock_router
from .auth_api import router as auth_router
from .workspaces_api import router as workspace_router
from .run_manager_api import router as run_manager_router
from admin_events import broadcast_run_event
from services.connection_pool import get_pool_stats, health_check as check_pool_health, get_postgres_pool, close_pools
from services.auth_middleware import AuthenticatedUser, OptionalUser, AdminUser
from services.workspace_service import get_workspace_service

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

api = FastAPI(title="Agentic SOP Orchestrator")

# Track background workflow tasks so we can cancel them.
RUN_TASKS: Dict[str, asyncio.Task] = {}

# Initialize AuthContext on API module load (for Hypercorn/Waitress workers)
# This ensures each worker process has AuthContext properly initialized
try:
    from services.credentials import AuthContext
    if not AuthContext.is_initialized():
        auth = AuthContext.initialize_from_env()
        print(f"[API] Initialized AuthContext for user: {auth.get_current_user().user_id}")
except Exception as e:
    print(f"[API] WARNING: Could not initialize AuthContext: {e}")
    print(f"[API] Credential-based skills may fail without user_context in inputs")

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

# Root endpoint (health check)
@api.get("/")
async def root():
    """Health check endpoint - returns API status"""
    return {
        "status": "ok",
        "service": "AgentSkills Framework",
        "version": "1.1.0"
    }

# Authentication endpoints
api.include_router(auth_router)

# Workspace endpoints
api.include_router(workspace_router)

# Run Manager endpoints (admin-only)
api.include_router(run_manager_router)

# Mock endpoints for hardcoded data (sandbox/testing)
api.include_router(mock_router)

@api.on_event("shutdown")
async def shutdown_cleanup():
    """Ensure background pools are closed on shutdown."""
    try:
        close_pools()
    except Exception as exc:
        emit_log(f"[API] Warning: Failed to close connection pools: {exc}")

class StartRequest(BaseModel):
    thread_id: str
    sop: str
    initial_data: Optional[Dict[str, Any]] = None  # Optional initial state
    run_name: Optional[str] = None  # Human-friendly name (optional)
    ack_key: Optional[str] = None  # Unique key for ACK handshake
    workspace_id: Optional[str] = None  # Target workspace (defaults to user's default)
    llm_model: Optional[str] = None  # Global LLM model (GPT/Grok/Gemini)
    callback_url: Optional[str] = None  # Webhook URL to call when run completes
    broadcast: bool = False  # Enable real-time broadcasts (default: False, opt-in)
    await_response: bool = False  # Wait for workflow completion before returning (default: False, fire-and-forget)

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

    # Resolve workspace (defaults to user's default)
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, req.workspace_id)
    workspace_id = workspace.id
    
    # STEP 1: Save metadata FIRST (track every run attempt, valid or not)
    await _save_run_metadata(
        req.thread_id,
        req.sop,
        req.initial_data or {},  # Default to empty dict if None
        run_name=run_name,
        user_id=current_user.id,
        workspace_id=workspace_id,
        llm_model=req.llm_model,  # Save as-is, validate next
        callback_url=req.callback_url,  # Store callback_url in metadata
    )
    
    # STEP 2: Send ACK via Pusher (UI will receive and redirect)
    if req.ack_key:
        await broadcast_run_event({
            "type": "ack",
            "ack_key": req.ack_key,
            "thread_id": req.thread_id,
            "run_name": run_name,
            "status": "accepted"
        })
    
    # Set log context so logs are tracked to this run
    set_log_context(req.thread_id, broadcast=req.broadcast)
    
    # STEP 3: Validate LLM model
    try:
        global_llm_model = _resolve_global_llm_model(req.llm_model)
    except ValueError as exc:
        error_msg = f"Invalid LLM model specified. {exc}"
        
        # Log the rejection to this run's log
        await publish_log(f"[RUN REJECTED] {error_msg}", req.thread_id)
        
        # Send rejection event so UI shows the error
        await broadcast_run_event({
            "type": "run_rejected",
            "thread_id": req.thread_id,
            "run_name": run_name,
            "error": error_msg,
            "reason": "invalid_model"
        })
        
        # Update metadata to mark as failed
        await _update_run_status(req.thread_id, "failed", error_message=error_msg)
        
        # Return error to caller
        raise HTTPException(status_code=400, detail=error_msg) from exc
    
    # Update metadata with validated model
    await _save_run_metadata(
        req.thread_id,
        req.sop,
        req.initial_data or {},
        run_name=run_name,
        user_id=current_user.id,
        workspace_id=workspace_id,
        llm_model=global_llm_model,  # Save validated model
        callback_url=req.callback_url,  # Store callback_url in metadata
    )

    # STEP 4: Create initial checkpoint
    config = {"configurable": {"thread_id": req.thread_id, "workspace_id": workspace_id}}
    initial_state = {
        "layman_sop": req.sop,
        "data_store": req.initial_data or {},  # Default to empty dict if None
        "history": ["Process Started"],
        "thread_id": req.thread_id,
        "workspace_id": workspace_id,
        "llm_model": global_llm_model,
        "execution_sequence": [],  # Track skill execution order for loop detection
        "_broadcast": req.broadcast,  # Store broadcast flag in state (controls log streaming only)
    }
    
    await app.aupdate_state(config, initial_state)
    
    # STEP 5: Broadcast workflow started event
    await broadcast_run_event({
        "type": "run_started",
        "thread_id": req.thread_id,
        "run_name": run_name,
        "user": current_user.username
    })
    
    # STEP 6: Log start
    emit_log(f"[API] Start requested for thread={req.thread_id} by user={current_user.username}", req.thread_id)
    await publish_log(f"[API] LLM model selected: {global_llm_model}", req.thread_id)
    await publish_log(f"[API] Log broadcast mode: {'enabled' if req.broadcast else 'disabled'}", req.thread_id)
    
    # STEP 7: Run workflow (will send progress updates via Pusher only if broadcast enabled)
    task = asyncio.create_task(_run_workflow(initial_state, config, broadcast=req.broadcast))
    RUN_TASKS[req.thread_id] = task
    task.add_done_callback(lambda t, thread_id=req.thread_id: RUN_TASKS.pop(thread_id, None))
    
    # STEP 8: Return response (await completion if requested)
    if req.await_response:
        # Wait for workflow to complete before returning
        try:
            data_store = await task
            return {
                "status": "completed", 
                "thread_id": req.thread_id, 
                "run_name": run_name, 
                "broadcast": req.broadcast,
                "workspace_id": workspace_id,
                "data_store": data_store  # Return final data_store
            }
        except Exception as exc:
            # If workflow failed, return error status
            error_msg = str(exc)
            emit_log(f"[API] Workflow failed for thread={req.thread_id}: {error_msg}", req.thread_id)
            return {
                "status": "failed",
                "thread_id": req.thread_id,
                "run_name": run_name,
                "broadcast": req.broadcast,
                "workspace_id": workspace_id,
                "error": error_msg
            }
    else:
        # Fire-and-forget: return immediately
        return {
            "status": "started", 
            "thread_id": req.thread_id, 
            "run_name": run_name, 
            "broadcast": req.broadcast,
            "workspace_id": workspace_id
        }


@api.post("/stop/{thread_id}")
async def stop_run(thread_id: str, current_user: AuthenticatedUser):
    """
    Stop a running workflow by forcing it to END with cancelled status.
    
    This will:
    1. Verify user owns the run
    2. Update state to force workflow to END
    3. Mark run as cancelled in database
    4. Broadcast cancellation event
    """
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id)
    
    try:
        # Cancel the running workflow task if it exists
        task = RUN_TASKS.get(thread_id)
        if not task or task.done():
            raise HTTPException(status_code=400, detail="Run is not active")

        emit_log(f"[API] Cancelling workflow task for thread={thread_id}")
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            emit_log(f"[API] Stop requested for thread={thread_id}, task did not cancel within timeout.")
        except asyncio.CancelledError:
            emit_log(f"[API] Workflow task cancelled for thread={thread_id}")

        await publish_log(f"[API] 🛑 STOP signal sent. Workflow task cancelled.", thread_id)

        # Update database status
        await _update_run_status(thread_id, "cancelled")
        
        # Broadcast cancellation event (always sent, admin events are lightweight)
        await broadcast_run_event({
            "type": "run_cancelled",
            "thread_id": thread_id,
            "cancelled_by": current_user.username
        })
        
        await publish_log(f"[API] Run {thread_id} cancelled by {current_user.username}", thread_id)
        
        return {
            "status": "cancelled",
            "thread_id": thread_id,
            "message": "Run has been stopped"
        }
        
    except HTTPException:
        raise
    except Exception as exc:
        emit_log(f"[API] Failed to stop run {thread_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to stop run: {str(exc)}")



async def _save_run_metadata(
    thread_id: str,
    sop: str,
    initial_data: Dict[str, Any],
    parent_thread_id: Optional[str] = None,
    run_name: Optional[str] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    llm_model: Optional[str] = None,
    callback_url: Optional[str] = None,
):
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
                
                # Build metadata JSONB with callback_url if provided
                metadata = {}
                if callback_url:
                    metadata['callback_url'] = callback_url
                
                # Insert run metadata
                cur.execute("""
                    INSERT INTO run_metadata (thread_id, run_name, sop, initial_data, parent_thread_id, rerun_count, status, user_id, workspace_id, llm_model, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, 'running', %s, %s, %s, %s)
                    ON CONFLICT (thread_id) DO UPDATE
                    SET run_name = EXCLUDED.run_name,
                        sop = EXCLUDED.sop,
                        initial_data = EXCLUDED.initial_data,
                        parent_thread_id = EXCLUDED.parent_thread_id,
                        rerun_count = EXCLUDED.rerun_count,
                        user_id = EXCLUDED.user_id,
                        workspace_id = EXCLUDED.workspace_id,
                        llm_model = EXCLUDED.llm_model,
                        metadata = EXCLUDED.metadata
                """, (thread_id, run_name, sop, json.dumps(initial_data or {}), parent_thread_id, rerun_count, user_id, workspace_id, llm_model, json.dumps(metadata)))
            conn.commit()
        finally:
            pool.putconn(conn)
    
    try:
        await asyncio.to_thread(_save_sync)
        # emit_log(f"[API] Saved run metadata for thread={thread_id}, name={run_name}, user_id={user_id}")
    except Exception as e:
        emit_log(f"[API] Failed to save run metadata: {e}")


async def _check_run_ownership(thread_id: str, user_id: str, is_admin: bool = False, workspace_id: Optional[str] = None):
    """
    Check if user owns a run
    
    Raises HTTPException if not owner or run not found
    """
    try:
        pool = get_postgres_pool()
    except RuntimeError:
        return  # Skip check if pool not available
    
    def _check_sync():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id::text, workspace_id::text FROM run_metadata WHERE thread_id = %s
                """, (thread_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return row
        finally:
            pool.putconn(conn)
    
    try:
        owner_workspace = await asyncio.to_thread(_check_sync)
        if owner_workspace is None:
            raise HTTPException(status_code=404, detail="Run not found")
        owner_id, run_workspace_id = owner_workspace
        if not is_admin and owner_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this run")
        if workspace_id and run_workspace_id and run_workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Run not found in workspace")
    except HTTPException:
        raise
    except Exception as e:
        emit_log(f"[API] Failed to check run ownership: {e}")


async def _update_run_status(thread_id: str, status: str, error_message: Optional[str] = None, failed_skill: Optional[str] = None):
    """Update the run status in run_metadata table and flush Redis checkpoints if completed."""
    try:
        pool = get_postgres_pool()
    except RuntimeError:
        emit_log("[API] Postgres pool not available, skipping run status update")
        return

    def _update_sync():
        from datetime import datetime
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE run_metadata
                    SET status = %s,
                        error_message = %s,
                        failed_skill = %s,
                        completed_at = %s
                    WHERE thread_id = %s
                """, (status, error_message, failed_skill, datetime.utcnow(), thread_id))
            conn.commit()
        finally:
            pool.putconn(conn)

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
        checkpoint_count = 0
        try:
            from services.checkpoint_buffer import RedisCheckpointBuffer
            from engine import _get_env_value, checkpointer
            
            db_uri = _get_env_value("DATABASE_URL", "")
            if db_uri:
                buffer = RedisCheckpointBuffer()
                
                # Get checkpoint count for error logging
                try:
                    checkpoints = await buffer.get_all_checkpoints(thread_id)
                    checkpoint_count = len(checkpoints)
                except:
                    pass
                
                success = await buffer.flush_to_postgres(thread_id, db_uri)
                if success:
                    emit_log(f"[API] Flushed checkpoints to PostgreSQL for {thread_id}")
                    
                    # Clear memory to prevent memory leaks (checkpoints now in PostgreSQL)
                    if hasattr(checkpointer, 'clear_thread_memory'):
                        checkpointer.clear_thread_memory(thread_id)
                        emit_log(f"[API] Cleared memory for {thread_id}")
                else:
                    # CRITICAL: Notify user about checkpoint flush failure
                    error_msg = (
                        "⚠️ WARNING: Failed to save execution logs to database. "
                        "The workflow completed but logs may be incomplete. "
                        "Please contact support if you need detailed execution history."
                    )
                    emit_log(f"[API] {error_msg}", thread_id=thread_id, level="ERROR")
                    
                    # Log to system_errors table for admin investigation
                    try:
                        from services.system_errors import log_system_error
                        await log_system_error(
                            error_type="checkpoint_flush_error",
                            severity="warning",
                            error_message=f"Checkpoint flush returned False for thread {thread_id}",
                            thread_id=thread_id,
                            error_context={
                                "checkpoint_count": checkpoint_count,
                                "db_uri_configured": bool(db_uri),
                                "status": status
                            }
                        )
                    except Exception as log_err:
                        emit_log(f"[API] Failed to log system error: {log_err}")
                    
                    # Broadcast error notification to user's UI
                    try:
                        await broadcast_run_event({
                            "thread_id": thread_id,
                            "type": "checkpoint_flush_error",
                            "message": error_msg,
                            "severity": "warning",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except Exception as broadcast_err:
                        emit_log(f"[API] Failed to broadcast checkpoint error: {broadcast_err}")
                
                await buffer.close()
        except Exception as e:
            # CRITICAL: Catch-all for any unexpected error during checkpoint flushing
            error_msg = (
                f"⚠️ CRITICAL ERROR: Checkpoint flush process failed for thread {thread_id}. "
                f"Logs and execution history may not be saved. Error: {str(e)[:200]}"
            )
            emit_log(f"[API] {error_msg}", thread_id=thread_id, level="ERROR")
            
            # Log to system_errors table for admin investigation (with full stack trace)
            try:
                from services.system_errors import log_checkpoint_flush_error
                await log_checkpoint_flush_error(
                    thread_id=thread_id,
                    error=e,
                    checkpoint_count=checkpoint_count,
                    is_critical=True
                )
            except Exception as log_err:
                emit_log(f"[API] Failed to log system error: {log_err}")
            
            # Broadcast critical error to user's UI
            try:
                await broadcast_run_event({
                    "thread_id": thread_id,
                    "type": "checkpoint_flush_critical_error",
                    "message": (
                        "⚠️ CRITICAL: Failed to save execution data. "
                        "Please contact support immediately. This workflow's logs may be lost."
                    ),
                    "severity": "critical",
                    "error_details": str(e)[:500],
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as broadcast_err:
                emit_log(f"[API] Failed to broadcast critical error: {broadcast_err}")
            
            import traceback
            traceback.print_exc()


async def _get_run_metadata(thread_id: str, workspace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve run metadata from database using connection pool."""
    try:
        pool = get_postgres_pool()
    except RuntimeError:
        emit_log("[API] Postgres pool not available, skipping run metadata retrieval")
        return None
    
    def _get_sync():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT thread_id, run_name, sop, initial_data, created_at, parent_thread_id, rerun_count, metadata,
                           status, error_message, failed_skill, completed_at, workspace_id::text, llm_model
                    FROM run_metadata
                    WHERE thread_id = %s
                """, (thread_id,))
                row = cur.fetchone()
                if row:
                    if workspace_id and row[12] and row[12] != workspace_id:
                        return None
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
                        "completed_at": row[11].isoformat() if row[11] else None,
                        "workspace_id": row[12],
                        "llm_model": row[13],
                    }
                return None
        finally:
            pool.putconn(conn)
    
    try:
        return await asyncio.to_thread(_get_sync)
    except Exception as e:
        emit_log(f"[API] Failed to get run metadata: {e}")
        return None


async def _get_run_metadata_for_callback(thread_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve minimal run metadata for callback webhook (optimized query).
    Only fetches essential fields to reduce query time and payload size.
    """
    try:
        pool = get_postgres_pool()
    except RuntimeError:
        emit_log("[API] Postgres pool not available, skipping callback metadata retrieval")
        return None
    
    def _get_sync():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                # Fetch callback_url and essential run info in one query
                cur.execute("""
                    SELECT thread_id, status, error_message, run_name, created_at, 
                           llm_model, failed_skill, completed_at, metadata
                    FROM run_metadata
                    WHERE thread_id = %s
                """, (thread_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "thread_id": row[0],
                        "status": row[1],
                        "error_message": row[2],
                        "run_name": row[3] or row[0],  # Default to thread_id if run_name is None
                        "created_at": row[4].isoformat() if row[4] else None,
                        "llm_model": row[5],
                        "failed_skill": row[6],
                        "completed_at": row[7].isoformat() if row[7] else None,
                        "callback_url": row[8].get("callback_url") if row[8] else None,
                    }
                return None
        finally:
            pool.putconn(conn)
    
    try:
        return await asyncio.to_thread(_get_sync)
    except Exception as e:
        emit_log(f"[API] Failed to get callback metadata: {e}")
        return None


async def _invoke_callback(thread_id: str):
    """
    Invoke the callback URL webhook if configured for this run.
    Fetches minimal run metadata and sends it as the payload.
    
    Optimized for high callback usage - single query fetches everything.
    """
    try:
        # Fetch metadata in single query (optimized for high callback usage)
        metadata = await _get_run_metadata_for_callback(thread_id)
        if not metadata:
            # Run not found in database
            return
        
        # Check if callback_url is configured (in-memory check, no extra query)
        callback_url = metadata.pop("callback_url", None)
        if not callback_url:
            # No callback configured, silently skip
            return
        
        await publish_log(f"[CALLBACK] Invoking webhook: {callback_url}", thread_id)
        
        # Send the minimal run metadata as payload (callback_url already removed)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(callback_url, json=metadata)
            response.raise_for_status()
            
        await publish_log(f"[CALLBACK] Webhook invoked successfully (status={response.status_code})", thread_id)
        emit_log(f"[CALLBACK] Successfully called callback for thread={thread_id}")
        
    except httpx.HTTPError as e:
        error_msg = f"HTTP error calling callback: {e}"
        await publish_log(f"[CALLBACK] {error_msg}", thread_id)
        emit_log(f"[CALLBACK] Failed to call callback for thread={thread_id}: {error_msg}")
    except Exception as e:
        error_msg = f"Error calling callback: {e}"
        await publish_log(f"[CALLBACK] {error_msg}", thread_id)
        emit_log(f"[CALLBACK] Failed to call callback for thread={thread_id}: {error_msg}")


async def _run_workflow(initial_state: Dict[str, Any], config: Dict[str, Any], broadcast: bool = False):
    """
    Run workflow in background without blocking the start endpoint.
    
    Args:
        initial_state: Initial workflow state
        config: Workflow configuration
        broadcast: Whether to send real-time broadcast events (default: False)
        
    Returns:
        Final data_store if workflow completes, None otherwise
    """
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    
    # Set the thread context for all logs in this workflow
    set_log_context(thread_id, broadcast=broadcast)
    
    try:
        # Use astream to enable real-time log broadcasting during execution
        async for _ in app.astream(initial_state, config):
            pass  # Logs are emitted in real-time as workflow executes
        
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
            # Fire-and-forget callback (don't wait for completion)
            asyncio.create_task(_invoke_callback(thread_id))
            return data_store  # Return data_store even on failure
        # Determine if truly completed or paused at an interrupt
        elif not next_nodes or (len(next_nodes) == 1 and next_nodes[0] == "__end__"):
            await _update_run_status(thread_id, "completed")
            await publish_log(f"[API] Workflow completed for thread={thread_id}", thread_id)
            # Fire-and-forget callback (don't wait for completion)
            asyncio.create_task(_invoke_callback(thread_id))
            return data_store  # Return final data_store
        elif "human_review" in next_nodes:
            await _update_run_status(thread_id, "paused")
            await publish_log(f"[API] Workflow paused at human_review (HITL) for thread={thread_id}", thread_id)
            return data_store  # Return data_store at pause point
        elif "await_callback" in next_nodes:
            await _update_run_status(thread_id, "paused")
            await publish_log(f"[API] Workflow paused awaiting callback for thread={thread_id}", thread_id)
            return data_store  # Return data_store at pause point
        else:
            await publish_log(f"[API] Workflow paused at {next_nodes} for thread={thread_id}", thread_id)
            return data_store  # Return data_store at pause point
            
    except asyncio.CancelledError:
        await publish_log(f"[API] Workflow task cancelled for thread={thread_id}", thread_id)
        await _update_run_status(thread_id, "cancelled")
        # Fire-and-forget callback (don't wait for completion)
        asyncio.create_task(_invoke_callback(thread_id))
        raise
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
            
            # Get updated state to return
            final_state = await app.aget_state(config)
            return final_state.values.get("data_store", {})
        except Exception as update_exc:
            emit_log(f"[API] Failed to update workflow state after error: {update_exc}")
            return {"_error": str(exc), "_status": "failed"}
        
        # Fire-and-forget callback (don't wait for completion)
        asyncio.create_task(_invoke_callback(thread_id))
    finally:
        RUN_TASKS.pop(thread_id, None)

@api.get("/status/{thread_id}")
async def get_status(thread_id: str, current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    config = {"configurable": {"thread_id": thread_id, "workspace_id": workspace.id}}
    
    # Check if user owns this run
    await _check_run_ownership(thread_id, current_user.id, current_user.is_admin, workspace.id)
    
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
    thread_id: str,
    current_user: AuthenticatedUser,
    updated_data: Optional[Dict[str, Any]] = Body(None),
    workspace_id: Optional[str] = None,
):
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    config = {"configurable": {"thread_id": thread_id, "workspace_id": workspace.id}}
    
    # Check if user owns this run
    await _check_run_ownership(thread_id, current_user.id, current_user.is_admin, workspace.id)
    
    # Update status to 'running' when resuming from HITL pause
    await _update_run_status(thread_id, "running")
    
    # If the human edited data, update the state first
    if updated_data:
        await app.aupdate_state(config, {"data_store": updated_data})
        await publish_log(f"[API] Human updated data for thread={thread_id} by user={current_user.username}", thread_id)
    
    await publish_log(f"[API] Human approval received; resuming thread={thread_id} by user={current_user.username}", thread_id)
    
    # Resume the graph using astream for real-time logs
    async for _ in app.astream(None, config):
        pass  # Logs are emitted in real-time as workflow resumes
    
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
async def list_runs(current_user: AuthenticatedUser, limit: int = 50, workspace_id: Optional[str] = None):
    """List workflow runs with computed status from database view."""
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    workspace_id = workspace.id

    # Try to use the database view for better performance
    db_uri = _get_env_value("DATABASE_URL", "")
    
    # Use run_metadata if DATABASE_URL is available (works with both direct PostgreSQL and buffered modes)
    if db_uri:
        try:
            pool = get_postgres_pool()

            def _fetch_from_metadata():
                conn = pool.getconn()
                try:
                    with conn.cursor() as cur:
                        if current_user.is_admin:
                            cur.execute("""
                                SELECT
                                    thread_id,
                                    run_name,
                                    parent_thread_id,
                                    rerun_count,
                                    status,
                                    created_at,
                                    error_message,
                                    failed_skill,
                                    user_id,
                                    workspace_id,
                                    llm_model
                                FROM run_metadata
                                WHERE workspace_id = %s
                                ORDER BY created_at DESC NULLS LAST
                                LIMIT %s
                            """, (workspace_id, limit))
                        else:
                            cur.execute("""
                                SELECT
                                    thread_id,
                                    run_name,
                                    parent_thread_id,
                                    rerun_count,
                                    status,
                                    created_at,
                                    error_message,
                                    failed_skill,
                                    user_id,
                                    workspace_id,
                                    llm_model
                                FROM run_metadata
                                WHERE user_id = %s AND workspace_id = %s
                                ORDER BY created_at DESC NULLS LAST
                                LIMIT %s
                            """, (current_user.id, workspace_id, limit))
                        
                        rows = cur.fetchall()
                        
                        return [
                            {
                                "thread_id": row[0],
                                "run_name": row[1],
                                # "sop": row[2],
                                # "initial_data": row[3],
                                "parent_thread_id": row[2],
                                "rerun_count": row[3],
                                "status": row[4],
                                "created_at": row[5].isoformat() if row[5] else None,
                                "error_message": row[6],
                                "failed_skill": row[7],
                                "user_id": row[8],
                                "workspace_id": row[9],
                                "llm_model": row[10],
                            }
                            for row in rows
                        ]
                finally:
                    pool.putconn(conn)
            
            runs = await asyncio.to_thread(_fetch_from_metadata)
            return {"runs": runs}
            
        except Exception as e:
            emit_log(f"[ADMIN] Failed to fetch runs from run_metadata, falling back to checkpointer: {e}")
    
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
async def run_detail(thread_id: str, current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id, current_user.is_admin, workspace.id)
    
    cp = checkpointer
    config = {"configurable": {"thread_id": thread_id, "workspace_id": workspace.id}}
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
async def get_logs(thread_id: str, current_user: AuthenticatedUser, limit: int = 1000, workspace_id: Optional[str] = None):
    """Retrieve historical logs for a specific thread."""
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id, current_user.is_admin, workspace.id)
    
    logs = await get_thread_logs(thread_id, limit)
    return {"logs": logs, "count": len(logs)}


@api.get("/admin/runs/{thread_id}/metadata")
async def get_run_metadata_endpoint(thread_id: str, current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    """Get run metadata for a specific thread."""
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    # Check ownership
    await _check_run_ownership(thread_id, current_user.id, current_user.is_admin, workspace.id)
    
    metadata = await _get_run_metadata(thread_id, workspace.id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Run metadata not found")
    return metadata


class RerunRequest(BaseModel):
    ack_key: Optional[str] = None  # Unique key for ACK handshake
    callback_url: Optional[str] = None  # Webhook URL to call when run completes
    broadcast: bool = False  # Enable real-time broadcasts (default: False, opt-in)

@api.post("/rerun/{thread_id}")
async def rerun_workflow(thread_id: str, current_user: AuthenticatedUser, req: RerunRequest = Body(default=RerunRequest()), workspace_id: Optional[str] = None):
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
    
    # Get the original run metadata
    metadata = await _get_run_metadata(thread_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Original run not found")

    # Resolve workspace
    target_workspace_id = metadata.get("workspace_id") or workspace_id
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, target_workspace_id)

    # Check ownership + workspace alignment
    await _check_run_ownership(thread_id, current_user.id, current_user.is_admin, workspace.id)
    
    # Generate new thread ID for this rerun
    new_thread_id = f"thread_{uuid.uuid4()}"
    
    # Generate new run name based on original
    original_run_name = metadata.get('run_name', thread_id)
    base_run_name = re.sub(r'\s*\(Rerun #\d+\)\s*$', '', original_run_name).strip()
    new_run_name = f"{base_run_name} (Rerun #{metadata['rerun_count'] + 1})"
    
    # STEP 1: Save metadata (track every run attempt, valid or not)
    await _save_run_metadata(
        new_thread_id,
        metadata["sop"],
        metadata["initial_data"],
        parent_thread_id=thread_id,
        run_name=new_run_name,
        user_id=current_user.id,
        workspace_id=workspace.id,
        llm_model=metadata.get("llm_model"),
        callback_url=req.callback_url,  # Use callback_url from rerun request if provided
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
    
    # Set log context so logs are tracked to this run
    set_log_context(new_thread_id, broadcast=req.broadcast)
    
    # STEP 3: Validate LLM model
    try:
        global_llm_model = _resolve_global_llm_model(metadata.get("llm_model"))
    except ValueError as exc:
        error_msg = f"Cannot rerun: Original run used model that is no longer valid. {exc}"
        
        # Log the rejection to this run's log
        await publish_log(f"[RERUN REJECTED] {error_msg}", new_thread_id)
        
        # Send rejection event so UI shows the error
        await broadcast_run_event({
            "type": "run_rejected",
            "thread_id": new_thread_id,
            "run_name": new_run_name,
            "parent_thread_id": thread_id,
            "error": error_msg,
            "reason": "invalid_model"
        })
        
        # Update metadata to mark as failed
        await _update_run_status(new_thread_id, "failed", error_message=error_msg)
        
        # Return error to caller
        raise HTTPException(status_code=400, detail=error_msg) from exc
    
    # STEP 4: Model is valid, create initial checkpoint
    config = {"configurable": {"thread_id": new_thread_id, "workspace_id": workspace.id, "broadcast": req.broadcast}}
    initial_state = {
        "layman_sop": metadata["sop"],
        "data_store": metadata["initial_data"],
        "history": [f"Process Started (Rerun from {base_run_name})"],
        "thread_id": new_thread_id,
        "workspace_id": workspace.id,
        "llm_model": global_llm_model,
        "execution_sequence": [],
        "_broadcast": req.broadcast,  # Store broadcast flag in state
    }
    await app.aupdate_state(config, initial_state)
    
    # STEP 5: Broadcast workflow started event
    await broadcast_run_event({
        "type": "run_started",
        "thread_id": new_thread_id,
        "run_name": new_run_name,
        "parent_thread_id": thread_id,
        "user": current_user.username
    })
    
    # STEP 6: Log start
    await publish_log(f"[API] Rerun requested from thread={thread_id} -> new thread={new_thread_id} by user={current_user.username}", new_thread_id)
    await publish_log(f"[API] LLM model selected: {global_llm_model}", new_thread_id)
    await publish_log(f"[API] Broadcast mode: {'enabled' if req.broadcast else 'disabled (logs only)'}", new_thread_id)
    
    # STEP 7: Run workflow (will send progress updates via Pusher only if broadcast enabled)
    task = asyncio.create_task(_run_workflow(initial_state, config, broadcast=req.broadcast))
    RUN_TASKS[new_thread_id] = task
    task.add_done_callback(lambda t, thread_id=new_thread_id: RUN_TASKS.pop(thread_id, None))
    
    # STEP 8: Return response
    return {
        "status": "started",
        "thread_id": new_thread_id,
        "run_name": new_run_name,
        "parent_thread_id": thread_id,
        "rerun_count": metadata["rerun_count"] + 1,
        "broadcast": req.broadcast
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

    # Resume the workflow - it will continue from await_callback node using astream for real-time logs
    async for _ in app.astream(None, config):
        pass  # Logs are emitted in real-time as workflow resumes
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


@api.get("/admin/system-errors")
async def get_system_errors(
    error_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    current_user: AdminUser = AdminUser
):
    """
    Retrieve unresolved system errors for admin investigation.
    
    Query Parameters:
        - error_type: Filter by error type (e.g., 'checkpoint_flush_error')
        - severity: Filter by severity ('warning', 'error', 'critical')
        - limit: Maximum number of errors to retrieve (default: 100, max: 1000)
    
    Returns:
        List of system error records with full details including stack traces
    """
    try:
        from services.system_errors import get_unresolved_errors
        
        # Enforce limit bounds
        limit = min(max(1, limit), 1000)
        
        errors = await get_unresolved_errors(
            error_type=error_type,
            severity=severity,
            limit=limit
        )
        
        return {
            "status": "success",
            "count": len(errors),
            "errors": errors,
            "filters": {
                "error_type": error_type,
                "severity": severity,
                "limit": limit
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system errors: {str(e)}")


@api.post("/admin/system-errors/{error_id}/resolve")
async def resolve_system_error(
    error_id: int,
    resolution_notes: Optional[str] = None,
    current_user: AdminUser = AdminUser
):
    """
    Mark a system error as resolved.
    
    Path Parameters:
        - error_id: ID of the error to resolve
    
    Body (optional):
        - resolution_notes: Notes about how the error was resolved
    
    Returns:
        Success status
    """
    try:
        from services.system_errors import resolve_error
        
        # Get username from current_user (AdminUser dependency)
        username = getattr(current_user, 'email', 'admin')
        
        success = await resolve_error(
            error_id=error_id,
            resolved_by=username,
            resolution_notes=resolution_notes
        )
        
        if success:
            return {
                "status": "success",
                "message": f"Error {error_id} marked as resolved",
                "error_id": error_id,
                "resolved_by": username
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Error {error_id} not found or already resolved"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve error: {str(e)}")


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
# Import LLM model management endpoints
from api.llm_models_api import *

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000)