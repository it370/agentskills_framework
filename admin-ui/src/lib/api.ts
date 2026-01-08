import { CheckpointTuple, RunEvent, RunListResponse } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";
const WS_BASE =
  process.env.NEXT_PUBLIC_WS_BASE?.replace(/\/$/, "") || "ws://localhost:8000";

export async function fetchRuns(limit = 50): Promise<CheckpointTuple[]> {
  const res = await fetch(`${API_BASE}/admin/runs?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to load runs: ${res.status}`);
  }
  const data = (await res.json()) as RunListResponse;
  return data.runs || [];
}

export async function fetchRunDetail(
  threadId: string
): Promise<CheckpointTuple> {
  const res = await fetch(`${API_BASE}/admin/runs/${threadId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Run not found: ${threadId}`);
  }
  return (await res.json()) as CheckpointTuple;
}

export function connectAdminEvents(onEvent: (event: RunEvent) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws/admin`);

  ws.onmessage = (evt) => {
    try {
      const parsed = JSON.parse(evt.data);
      if (parsed?.type === "run_event") {
        onEvent(parsed.data as RunEvent);
      }
    } catch (e) {
      console.warn("Failed to parse admin event", e);
    }
  };

  return ws;
}

export function connectLogs(onLog: (line: string) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws/logs`);
  
  ws.onopen = () => {
    console.log("[API] Logs websocket connected");
  };
  
  ws.onmessage = (evt) => {
    console.log("[API] Log received:", evt.data);
    onLog(evt.data as string);
  };
  
  ws.onerror = (err) => {
    console.error("[API] Logs websocket error:", err);
  };
  
  ws.onclose = () => {
    console.log("[API] Logs websocket closed");
  };
  
  return ws;
}

