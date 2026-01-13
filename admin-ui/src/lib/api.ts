import { CheckpointTuple, RunEvent, RunListResponse, RunSummary } from "./types";
import { getApiBase, getWsBase } from "./config";

const API_BASE = getApiBase();
const WS_BASE = getWsBase();

export async function fetchRuns(limit = 50): Promise<(CheckpointTuple | RunSummary)[]> {
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

export async function fetchThreadLogs(
  threadId: string,
  limit = 1000
): Promise<Array<{ id: number; thread_id: string; message: string; created_at: string; level: string }>> {
  const res = await fetch(`${API_BASE}/admin/runs/${threadId}/logs?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch logs for thread: ${threadId}`);
  }
  const data = await res.json();
  return data.logs || [];
}

export async function approveStep(
  threadId: string,
  updatedData?: Record<string, any>
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/approve/${threadId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: updatedData ? JSON.stringify(updatedData) : null,
  });
  if (!res.ok) {
    throw new Error(`Failed to approve step for thread: ${threadId}`);
  }
  return await res.json();
}

export async function rerunWorkflow(
  threadId: string
): Promise<{ status: string; thread_id: string; parent_thread_id: string; rerun_count: number }> {
  const res = await fetch(`${API_BASE}/rerun/${threadId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to rerun workflow: ${res.status} - ${errorText}`);
  }
  return await res.json();
}

export async function getRunMetadata(
  threadId: string
): Promise<{
  thread_id: string;
  run_name?: string;
  sop: string;
  initial_data: Record<string, any>;
  created_at: string;
  parent_thread_id?: string;
  rerun_count: number;
  metadata: Record<string, any>;
  status?: string;
  error_message?: string;
  failed_skill?: string;
  completed_at?: string;
}> {
  const res = await fetch(`${API_BASE}/admin/runs/${threadId}/metadata`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Run metadata not found: ${threadId}`);
  }
  return await res.json();
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

export function connectLogs(onLog: (line: string, threadId?: string) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws/logs`);
  
  ws.onopen = () => {
    console.log("[API] Logs websocket connected");
  };
  
  ws.onmessage = (evt) => {
    console.log("[API] Log received:", evt.data);
    try {
      // Try to parse as JSON first (new structured format)
      const parsed = JSON.parse(evt.data);
      if (parsed.text !== undefined) {
        onLog(parsed.text, parsed.thread_id);
        return;
      }
    } catch {
      // Fall back to plain text for backward compatibility
    }
    // Plain text format
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

// --- SKILL MANAGEMENT API ---

export interface Skill {
  name: string;
  description: string;
  requires: string[];
  produces: string[];
  optional_produces?: string[];
  executor: "llm" | "rest" | "action";
  hitl_enabled?: boolean;
  prompt?: string;
  system_prompt?: string;
  rest_config?: {
    url: string;
    method: string;
    timeout?: number;
    headers?: Record<string, string>;
  };
  action_config?: {
    type: string;
    module?: string;
    function?: string;
    query?: string;
    source?: string;
    credential_ref?: string;
  };
  action_code?: string;
  source?: string;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export async function fetchSkills(): Promise<{skills: Skill[], count: number}> {
  const res = await fetch(`${API_BASE}/admin/skills`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch skills: ${res.status}`);
  }
  return await res.json();
}

export async function fetchSkill(name: string): Promise<Skill> {
  const res = await fetch(`${API_BASE}/admin/skills/${encodeURIComponent(name)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch skill: ${res.status}`);
  }
  return await res.json();
}

export async function createSkill(skill: Skill): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/skills`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(skill),
  });
  if (!res.ok) {
    let errorMessage = `Failed to create skill (${res.status})`;
    try {
      const errorData = await res.json();
      if (errorData.detail) {
        // If detail is an object (validation error), format it nicely
        if (typeof errorData.detail === 'object') {
          const err = errorData.detail;
          errorMessage = `${err.error || 'Validation Error'}: ${err.message || ''}`;
          if (err.field) errorMessage += ` (in ${err.field})`;
          if (err.line) errorMessage += ` at line ${err.line}`;
          if (err.text) errorMessage += `\n  → ${err.text}`;
          if (err.hint) errorMessage += `\n\n${err.hint}`;
        } else {
          errorMessage = errorData.detail;
        }
      }
    } catch {
      errorMessage += `: ${await res.text()}`;
    }
    throw new Error(errorMessage);
  }
  return await res.json();
}

export async function updateSkill(name: string, updates: Partial<Skill>): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/skills/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    let errorMessage = `Failed to update skill (${res.status})`;
    try {
      const errorData = await res.json();
      if (errorData.detail) {
        // If detail is an object (validation error), format it nicely
        if (typeof errorData.detail === 'object') {
          const err = errorData.detail;
          errorMessage = `${err.error || 'Validation Error'}: ${err.message || ''}`;
          if (err.field) errorMessage += ` (in ${err.field})`;
          if (err.line) errorMessage += ` at line ${err.line}`;
          if (err.text) errorMessage += `\n  → ${err.text}`;
          if (err.hint) errorMessage += `\n\n${err.hint}`;
        } else {
          errorMessage = errorData.detail;
        }
      }
    } catch {
      errorMessage += `: ${await res.text()}`;
    }
    throw new Error(errorMessage);
  }
  return await res.json();
}

export async function deleteSkill(name: string): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/skills/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Failed to delete skill: ${error}`);
  }
  return await res.json();
}

export async function reloadSkills(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/skills/reload`, {
    method: "POST",
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Failed to reload skills: ${error}`);
  }
  return await res.json();
}

