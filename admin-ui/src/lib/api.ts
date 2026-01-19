import { CheckpointTuple, RunEvent, RunListResponse, RunSummary } from "./types";
import Pusher from "pusher-js";
import { getAuthHeaders } from "./auth";
import { getActiveWorkspaceId } from "./workspaceStorage";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

// Pusher configuration
const PUSHER_KEY = process.env.NEXT_PUBLIC_PUSHER_KEY || "";
const PUSHER_CLUSTER = process.env.NEXT_PUBLIC_PUSHER_CLUSTER || "ap2";

function withWorkspace(url: string, workspaceId?: string | null): string {
  if (!workspaceId) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}workspace_id=${encodeURIComponent(workspaceId)}`;
}

export async function fetchRuns(limit = 50): Promise<(CheckpointTuple | RunSummary)[]> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/runs?limit=${limit}`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
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
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/runs/${threadId}`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
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
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/runs/${threadId}/logs?limit=${limit}`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
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
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/approve/${threadId}`, workspaceId), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: updatedData ? JSON.stringify(updatedData) : null,
  });
  if (!res.ok) {
    throw new Error(`Failed to approve step for thread: ${threadId}`);
  }
  return await res.json();
}

export async function stopRun(threadId: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/stop/${threadId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to stop run: ${errorText}`);
  }
  return await res.json();
}

export async function rerunWorkflow(
  threadId: string,
  ackKey?: string
): Promise<{ status: string; thread_id: string; parent_thread_id: string; rerun_count: number; run_name?: string }> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/rerun/${threadId}`, workspaceId), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      ack_key: ackKey,
    }),
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
  workspace_id?: string;
}> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/runs/${threadId}/metadata`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Run metadata not found: ${threadId}`);
  }
  return await res.json();
}


export function connectAdminEvents(onEvent: (RunEvent) => void): { disconnect: () => void } {
  // Use Pusher for real-time admin events
  const pusher = new Pusher(PUSHER_KEY, {
    cluster: PUSHER_CLUSTER,
    enabledTransports: ['ws', 'wss'],
    forceTLS: true,
  });
  
  const channel = pusher.subscribe('admin');
  
  channel.bind('admin_event', (data: any) => {
    try {
      if (data?.type === "run_event" && data.data) {
        onEvent(data.data as RunEvent);
      }
    } catch (e) {
      console.warn("[PUSHER] Failed to parse admin event", e);
    }
  });
  
  channel.bind('pusher:subscription_error', (error: any) => {
    console.error("[PUSHER] Admin events subscription error:", error);
  });
  
  pusher.connection.bind('error', (err: any) => {
    console.error("[PUSHER] Connection error:", err);
  });
  
  return {
    disconnect: () => {
      channel.unbind_all();
      channel.unsubscribe();
      pusher.disconnect();
    }
  };
}

export function connectLogs(onLog: (line: string, threadId?: string) => void): { disconnect: () => void } {
  // Use Pusher for real-time logs
  const pusher = new Pusher(PUSHER_KEY, {
    cluster: PUSHER_CLUSTER,
    enabledTransports: ['ws', 'wss'],
    forceTLS: true,
  });
  
  const channel = pusher.subscribe('logs');
  
  channel.bind('log', (data: any) => {
    try {
      if (data.text !== undefined) {
        onLog(data.text, data.thread_id);
      } else {
        console.warn("[PUSHER] Message missing 'text' field:", data);
      }
    } catch (e) {
      console.error("[PUSHER] Error processing log:", e);
    }
  });
  
  channel.bind('pusher:subscription_error', (error: any) => {
    console.error("[PUSHER] Logs subscription error:", error);
  });
  
  pusher.connection.bind('error', (err: any) => {
    console.error("[PUSHER] Connection error:", err);
  });
  
  return {
    disconnect: () => {
      channel.unbind_all();
      channel.unsubscribe();
      pusher.disconnect();
    }
  };
}

// --- SKILL MANAGEMENT API ---

export interface Skill {
  id?: string; // UUID
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
  action_functions?: string;
  source?: string;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
  workspace_id?: string;
  owner_id?: string;
  is_public?: boolean;
}

export async function fetchSkills(): Promise<{skills: Skill[], count: number}> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch skills: ${res.status}`);
  }
  return await res.json();
}

export async function fetchSkill(name: string): Promise<Skill> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills/${encodeURIComponent(name)}`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch skill: ${res.status}`);
  }
  return await res.json();
}

export async function fetchSkillById(id: string): Promise<Skill> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills/${encodeURIComponent(id)}`, workspaceId), {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch skill: ${res.status}`);
  }
  return await res.json();
}

export async function createSkill(skill: Skill): Promise<any> {
  const workspaceId = getActiveWorkspaceId();
  const payload = { ...skill, workspace_id: workspaceId };
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills`, workspaceId), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
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

export async function updateSkill(skillIdOrName: string, updates: Partial<Skill>): Promise<any> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills/${encodeURIComponent(skillIdOrName)}`, workspaceId), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ ...updates, workspace_id: workspaceId }),
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

export async function deleteSkill(skillIdOrName: string): Promise<any> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills/${encodeURIComponent(skillIdOrName)}`, workspaceId), {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Failed to delete skill: ${error}`);
  }
  return await res.json();
}

export async function reloadSkills(): Promise<any> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(withWorkspace(`${API_BASE}/admin/skills/reload`, workspaceId), {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Failed to reload skills: ${error}`);
  }
  return await res.json();
}

