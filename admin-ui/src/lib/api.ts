import { CheckpointTuple, RunEvent, RunListResponse, RunSummary } from "./types";
import { adminEvents } from "./adminEvents";
import { getAuthHeaders } from "./auth";
import { getActiveWorkspaceId } from "./workspaceStorage";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

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

export async function fetchThreadWorkflowUiEvents(
  threadId: string,
  limit = 2000
): Promise<RunEvent[]> {
  const workspaceId = getActiveWorkspaceId();
  const res = await fetch(
    withWorkspace(`${API_BASE}/admin/runs/${threadId}/workflow-ui-events?limit=${limit}`, workspaceId),
    {
      cache: "no-store",
      headers: getAuthHeaders(),
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch workflow UI events for thread: ${threadId}`);
  }
  const data = await res.json();
  return (data.events || []) as RunEvent[];
}

export async function fetchAdminConfig(configKey: string): Promise<{
  key: string;
  value: any;
  description?: string;
  updated_by?: string;
  updated_at?: string;
}> {
  const res = await fetch(`${API_BASE}/admin/config/${encodeURIComponent(configKey)}`, {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch config: ${configKey}`);
  }
  return await res.json();
}

export async function updateAdminConfig(
  configKey: string,
  value: any,
  description?: string
): Promise<{ status: string; config: { key: string; value: any } }> {
  const res = await fetch(`${API_BASE}/admin/config/${encodeURIComponent(configKey)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ value, description }),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to update config: ${errorText}`);
  }
  return await res.json();
}

export async function isAgenticViewEnabled(): Promise<boolean> {
  try {
    const config = await fetchAdminConfig("feature.agentic_view_enabled");
    const raw = config?.value;
    if (typeof raw === "boolean") return raw;
    if (raw && typeof raw === "object" && "enabled" in raw) {
      return Boolean((raw as Record<string, unknown>).enabled);
    }
    return true;
  } catch {
    return true;
  }
}

export async function approveStep(
  threadId: string,
  updatedData?: Record<string, any>
): Promise<{ status: string }> {
  const workspaceId = getActiveWorkspaceId();
  
  // Always enable broadcast from UI
  const payload = {
    updated_data: updatedData,
    broadcast: true,
  };
  
  const res = await fetch(withWorkspace(`${API_BASE}/approve/${threadId}`, workspaceId), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
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
      broadcast: true,  // Enable real-time broadcasts for UI
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
  llm_model?: string | null;
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


/** Subscribe to admin run events via the shared SSE admin stream. */
export function connectAdminEvents(onEvent: (event: RunEvent) => void): { disconnect: () => void } {
  const unsubscribe = adminEvents.on("*", (event: any) => {
    try {
      const eventType = event?.type || event?.event || "unknown";
      const eventThreadId = event?.thread_id || "n/a";
      console.info(`[AdminEvents][global] ${eventType}`, { thread_id: eventThreadId, event });
      onEvent(event as RunEvent);
    } catch (e) {
      console.warn("[SSE] Failed to handle admin event", e);
    }
  });
  return { disconnect: unsubscribe };
}

/** Subscribe to admin events for a single thread via scoped SSE stream. */
export function connectThreadAdminEvents(
  threadId: string,
  onEvent: (event: RunEvent) => void
): { disconnect: () => void } {
  const url = `${API_BASE}/api/admin-events/${encodeURIComponent(threadId)}/stream`;
  const abort = new AbortController();
  console.info(`[AdminEvents][thread:${threadId}] connect`, { url });

  (async () => {
    while (!abort.signal.aborted) {
      try {
        const res = await fetch(url, {
          headers: getAuthHeaders(),
          signal: abort.signal,
        });
        console.info(`[AdminEvents][thread:${threadId}] response`, {
          ok: res.ok,
          status: res.status,
          statusText: res.statusText,
        });
        if (!res.ok || !res.body) {
          await new Promise((r) => setTimeout(r, 3000));
          continue;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                const event = (data?.data ?? data) as RunEvent;
                const eventType = event?.type || event?.event || "unknown";
                console.info(`[AdminEvents][thread:${threadId}] ${eventType}`, event);
                onEvent(event);
              } catch (_) {}
            }
          }
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        console.warn("[AdminEvents] Thread SSE error, reconnecting in 3s:", e);
      }
      await new Promise((r) => setTimeout(r, 3000));
    }
  })();

  return {
    disconnect: () => {
      console.info(`[AdminEvents][thread:${threadId}] disconnect`);
      abort.abort();
    },
  };
}

/**
 * Connect to the live log SSE stream.
 *
 * @param onLog - Called with each log line and its thread_id.
 * @param threadId - Optional: subscribe to a per-thread stream. Omit for the global stream.
 */
export function connectLogs(
  onLog: (line: string, threadId?: string) => void,
  threadId?: string
): { disconnect: () => void } {
  const url = threadId
    ? `${API_BASE}/api/runs/${encodeURIComponent(threadId)}/logs/stream`
    : `${API_BASE}/api/logs/stream`;
  const abort = new AbortController();
  (async () => {
    while (!abort.signal.aborted) {
      try {
        const res = await fetch(url, {
          headers: getAuthHeaders(),
          signal: abort.signal,
        });
        if (!res.ok || !res.body) {
          await new Promise((r) => setTimeout(r, 3000));
          continue;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            const normalized = line.replace(/\r$/, "");
            if (!normalized.trim()) continue;
            if (/^data:\s*/i.test(normalized)) {
              const rawData = normalized.replace(/^data:\s*/i, "");
              try {
                const data = JSON.parse(rawData);
                if (data?.text !== undefined) onLog(data.text, data.thread_id);
              } catch (error) {
                console.warn("[LiveLog SSE] Failed to parse payload", error);
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        console.warn("[SSE] Log stream error, reconnecting in 3s:", e);
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
  })();

  return {
    disconnect: () => abort.abort(),
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
  llm_model?: string | null;
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

export type LlmModelOption = {
  model_name: string;
  provider?: string;
  is_active?: boolean;
  is_default?: boolean;
};

export async function fetchLlmModels(includeInactive = false): Promise<LlmModelOption[]> {
  const url = includeInactive ? `${API_BASE}/admin/llm-models?include_inactive=true` : `${API_BASE}/admin/llm-models`;
  const res = await fetch(url, {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch LLM models: ${res.status}`);
  }
  const data = await res.json();
  return data.models || [];
}

export async function createLlmModel(payload: {
  provider: string;
  model_name: string;
  api_key: string;
  is_active?: boolean;
  is_default?: boolean;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/llm-models`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to create LLM model: ${errorText}`);
  }
  return await res.json();
}

export async function updateLlmModel(modelName: string, updates: {
  provider?: string;
  api_key?: string;
  is_active?: boolean;
  is_default?: boolean;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/llm-models/${encodeURIComponent(modelName)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to update LLM model: ${errorText}`);
  }
  return await res.json();
}

export async function deleteLlmModel(modelName: string): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/llm-models/${encodeURIComponent(modelName)}`, {
    method: "DELETE",
    headers: {
      ...getAuthHeaders(),
    },
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to delete LLM model: ${errorText}`);
  }
  return await res.json();
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

// --- RUN MANAGER API ---

export interface RunListItem {
  id: string;
  name?: string;
  result?: string;
  time?: string;
  username?: string;
  workspace?: string;
  workspace_name?: string;
}

export interface RunManagerListResponse {
  runs: RunListItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchRunsManager(params: {
  page?: number;
  page_size?: number;
  username?: string;
  workspace?: string;
  search?: string;
}): Promise<RunManagerListResponse> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.append("page", params.page.toString());
  if (params.page_size) searchParams.append("page_size", params.page_size.toString());
  if (params.username) searchParams.append("username", params.username);
  if (params.workspace) searchParams.append("workspace", params.workspace);
  if (params.search) searchParams.append("search", params.search);

  const res = await fetch(`${API_BASE}/admin/run-manager/runs?${searchParams.toString()}`, {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to load runs: ${res.status}`);
  }
  return await res.json();
}

export async function deleteRunsBulk(threadIds: string[]): Promise<{ deleted_count: number; failed: Array<{ thread_id: string; error: string }> }> {
  const res = await fetch(`${API_BASE}/admin/run-manager/runs`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ thread_ids: threadIds }),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to delete runs: ${errorText}`);
  }
  return await res.json();
}

export async function fetchRunManagerUsernames(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/admin/run-manager/usernames`, {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to load usernames: ${res.status}`);
  }
  const data = await res.json();
  return data.usernames || [];
}

export async function fetchRunManagerWorkspaces(): Promise<Array<{ id: string; name: string; username?: string }>> {
  const res = await fetch(`${API_BASE}/admin/run-manager/workspaces`, {
    cache: "no-store",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to load workspaces: ${res.status}`);
  }
  const data = await res.json();
  return data.workspaces || [];
}

