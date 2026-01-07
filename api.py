from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel

from engine import AgentState, app
import log_stream

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
        "history": ["Process Started"]
    }
    # Run until it hits an END or an INTERRUPT
    result = await app.ainvoke(initial_state, config)
    return {"status": "running_or_paused", "state": result}

@api.get("/status/{thread_id}")
async def get_status(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = await app.aget_state(config)
    next_nodes = state.next or []
    is_human_review = "human_review" in next_nodes
    return {
        "is_paused": len(next_nodes) > 0,
        "is_human_review": is_human_review,
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
    
    # Resume the graph
    await app.ainvoke(None, config)
    return {"status": "resumed"}


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