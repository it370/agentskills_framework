import asyncio
from typing import Any, Dict, Optional

import httpx
from fastapi import Body, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel
from engine import AgentState, app
import log_stream
from log_stream import publish_log, emit_log

api = FastAPI(title="Agentic SOP Orchestrator")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


broadcast_task = None


@api.on_event("startup")
async def _start_broadcast():
    # No background loop needed; publish is immediate. Placeholder for future.
    pass


@api.on_event("shutdown")
async def _stop_broadcast():
    pass

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
    await publish_log(f"[API] Start requested for thread={req.thread_id}")
    # Run until it hits an END or an INTERRUPT
    result = await app.ainvoke(initial_state, config)
    return {"status": "running_or_paused", "state": result}

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
        print(f"[API] Human updated data for {thread_id}")
    
    await publish_log(f"[API] Approval received; resuming thread={thread_id}")
    # Resume the graph
    await app.ainvoke(None, config)
    return {"status": "resumed"}

class CallbackPayload(BaseModel):
    thread_id: str
    skill: str
    data: Dict[str, Any]
    error: Optional[str] = None

@api.post("/callback")
async def rest_callback(req: CallbackPayload):
    config = {"configurable": {"thread_id": req.thread_id}}
    state = await app.aget_state(config)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown thread_id")

    current_values = state.values or {}
    data_store = current_values.get("data_store", {}) or {}
    history = list(current_values.get("history") or [])

    await publish_log(f"[CALLBACK] Received results for thread={req.thread_id}, skill={req.skill}")

    merged = {**data_store, **req.data}
    # Clear pending REST marker if present
    if "_rest_pending" in merged:
        pending = set(merged.get("_rest_pending") or [])
        pending.discard(req.skill)
        if pending:
            merged["_rest_pending"] = list(pending)
        else:
            merged.pop("_rest_pending", None)

    history.append(f"Executed {req.skill} (REST callback)")
    if req.error:
        history.append(f"Error from {req.skill}: {req.error}")

    await app.aupdate_state(config, {
        "data_store": merged,
        "history": history,
        "active_skill": None,
    })

    await app.ainvoke(None, config)
    await publish_log(f"[CALLBACK] Applied results and resumed thread={req.thread_id}")
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
    """
    await publish_log(f"[DEMO REST] Received request for skill={req.skill}, thread={req.thread_id}")

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
            async with httpx.AsyncClient() as client:
                await client.post(req.callback_url, json=payload)
            emit_log(f"[DEMO REST] Callback sent for thread={req.thread_id}")
        except Exception as exc:
            emit_log(f"[DEMO REST] Callback failed for thread={req.thread_id}: {exc}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000)