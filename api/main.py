import os
import asyncio
import threading
import json
from typing import Any, Dict, Optional
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel
from psycopg import Connection as SyncConnection

from engine import AgentState, app, _deep_merge_dict, checkpointer, _safe_serialize, _get_env_value, _AsyncPostgresSaver
import log_stream
from log_stream import publish_log, emit_log, set_log_context, get_thread_logs
from .mock_api import router as mock_router
from env_loader import load_env_once
from admin_events import broadcast_run_event, register_admin, unregister_admin

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

# Mock endpoints for hardcoded data (sandbox/testing)
api.include_router(mock_router)

broadcast_task = None
run_event_listener_thread = None
_listener_stop_flag = threading.Event()

def _sync_run_event_listener(db_uri: str):
    """Synchronous LISTEN in a thread (Windows-compatible)."""
    try:
        conn = SyncConnection.connect(db_uri, autocommit=True)
        conn.execute("LISTEN run_events")
        emit_log("[ADMIN] Listening for Postgres run_events notifications (sync mode).")
        
        while not _listener_stop_flag.is_set():
            conn.execute("SELECT 1")  # keep-alive
            for notify in conn.notifies():
                try:
                    payload = json.loads(notify.payload)
                except Exception:
                    payload = {"raw": notify.payload}
                # Forward to async broadcast from thread
                asyncio.run_coroutine_threadsafe(broadcast_run_event(payload), asyncio.get_event_loop())
        
        conn.close()
        emit_log("[ADMIN] Run event listener stopped.")
    except Exception as exc:
        emit_log(f"[ADMIN] Run event listener error: {exc}")


async def _maybe_start_run_event_listener():
    global run_event_listener_thread
    if run_event_listener_thread and run_event_listener_thread.is_alive():
        return
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = _get_env_value("DATABASE_URL", "")
    if not db_uri:
        emit_log("[ADMIN] DATABASE_URL not set; run event listener disabled.")
        return
    
    _listener_stop_flag.clear()
    run_event_listener_thread = threading.Thread(target=_sync_run_event_listener, args=(db_uri,), daemon=True)
    run_event_listener_thread.start()


async def _stop_run_event_listener():
    global run_event_listener_thread
    if run_event_listener_thread and run_event_listener_thread.is_alive():
        _listener_stop_flag.set()
        run_event_listener_thread.join(timeout=2)


@api.on_event("startup")
async def _start_broadcast():
    # No background loop needed; publish is immediate. Placeholder for future.
    await _maybe_start_run_event_listener()


@api.on_event("shutdown")
async def _stop_broadcast():
    await _stop_run_event_listener()

class StartRequest(BaseModel):
    thread_id: str
    sop: str
    initial_data: Dict[str, Any]

@api.post("/start")
async def start_process(req: StartRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    initial_state = {
        "layman_sop": req.sop,
        "data_store": req.initial_data,
        "history": ["Process Started"],
        "thread_id": req.thread_id,
    }
    await publish_log(f"[API] Start requested for thread={req.thread_id}", req.thread_id)
    
    # Run the workflow in the background to avoid blocking the response
    asyncio.create_task(_run_workflow(initial_state, config))
    
    return {"status": "started", "thread_id": req.thread_id}


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
        
        # Determine if truly completed or paused at an interrupt
        if not next_nodes or (len(next_nodes) == 1 and next_nodes[0] == "__end__"):
            await publish_log(f"[API] Workflow completed for thread={thread_id}", thread_id)
        elif "human_review" in next_nodes:
            await publish_log(f"[API] Workflow paused at human_review for thread={thread_id}", thread_id)
        elif "await_callback" in next_nodes:
            await publish_log(f"[API] Workflow paused awaiting callback for thread={thread_id}", thread_id)
        else:
            await publish_log(f"[API] Workflow paused at {next_nodes} for thread={thread_id}", thread_id)
            
    except Exception as exc:
        await publish_log(f"[API] Workflow error for thread={thread_id}: {exc}", thread_id)

@api.get("/status/{thread_id}")
async def get_status(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = await app.aget_state(config)
    next_nodes = state.next or []
    is_human_review = "human_review" in next_nodes
    is_waiting_callback = "await_callback" in next_nodes
    return {
        "is_paused": len(next_nodes) > 0,
        "is_human_review": is_human_review,
        "is_waiting_callback": is_waiting_callback,
        "next_node": next_nodes,
        "active_skill": state.values.get("active_skill"),
        "data": state.values.get("data_store"),
        "history": state.values.get("history")
    }

@api.post("/approve/{thread_id}")
async def approve_step(
    thread_id: str, updated_data: Optional[Dict[str, Any]] = Body(None)
):
    config = {"configurable": {"thread_id": thread_id}}
    
    # If the human edited data, update the state first
    if updated_data:
        await app.aupdate_state(config, {"data_store": updated_data})
        await publish_log(f"[API] Human updated data for thread={thread_id}", thread_id)
    
    await publish_log(f"[API] Human approval received; resuming thread={thread_id}", thread_id)
    
    # Resume the graph
    await app.ainvoke(None, config)
    
    # Check the state after resuming
    state = await app.aget_state(config)
    next_nodes = state.next or []
    
    # Log appropriate status
    if not next_nodes or (len(next_nodes) == 1 and next_nodes[0] == "__end__"):
        await publish_log(f"[API] Workflow completed after approval for thread={thread_id}", thread_id)
    elif "human_review" in next_nodes:
        await publish_log(f"[API] Workflow paused again at human_review for thread={thread_id}", thread_id)
    elif "await_callback" in next_nodes:
        await publish_log(f"[API] Workflow paused awaiting callback for thread={thread_id}", thread_id)
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
async def list_runs(limit: int = 50):
    """List workflow runs with computed status from database view."""
    # Try to use the database view for better performance
    db_uri = _get_env_value("DATABASE_URL", "")
    
    if db_uri and isinstance(checkpointer, _AsyncPostgresSaver):
        # Use database view with pre-computed status
        try:
            import psycopg
            
            def _fetch_from_view():
                with psycopg.connect(db_uri, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT 
                                thread_id,
                                checkpoint_id,
                                checkpoint_ns,
                                active_skill,
                                history_count,
                                status,
                                sop_preview,
                                updated_at,
                                checkpoint,
                                metadata
                            FROM run_list_view
                            ORDER BY updated_at DESC NULLS LAST
                            LIMIT %s
                        """, (limit,))
                        rows = cur.fetchall()
                        
                        return [
                            {
                                "thread_id": row[0],
                                "checkpoint_id": row[1],
                                "checkpoint_ns": row[2],
                                "active_skill": row[3],
                                "history_count": row[4],
                                "status": row[5],
                                "sop_preview": row[6],
                                "updated_at": row[7].isoformat() if row[7] else None,
                                "checkpoint": row[8],
                                "metadata": row[9],
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
async def run_detail(thread_id: str):
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
async def get_logs(thread_id: str, limit: int = 1000):
    """Retrieve historical logs for a specific thread."""
    logs = await get_thread_logs(thread_id, limit)
    return {"logs": logs, "count": len(logs)}


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


@api.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    await log_stream.register(websocket)
    try:
        while True:
            # Keep the connection open; clients need not send data.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await log_stream.unregister(websocket)


@api.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket):
    await websocket.accept()
    await register_admin(websocket)
    try:
        while True:
            # Keep the connection open; clients need not send data.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await unregister_admin(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000)