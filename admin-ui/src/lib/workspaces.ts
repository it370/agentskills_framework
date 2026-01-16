import { getAuthHeaders } from "./auth";
import { getActiveWorkspaceId, setActiveWorkspaceId } from "./workspaceStorage";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export interface Workspace {
  id: string;
  name: string;
  user_id?: string;
  is_default: boolean;
  created_at?: string;
  updated_at?: string;
}

export async function fetchWorkspaces(): Promise<{
  workspaces: Workspace[];
  default_workspace_id?: string | null;
}> {
  const res = await fetch(`${API_BASE}/workspaces`, {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to load workspaces (${res.status})`);
  }
  const data = await res.json();
  const { workspaces = [], default_workspace_id } = data;
  if (!getActiveWorkspaceId() && default_workspace_id) {
    setActiveWorkspaceId(default_workspace_id);
  }
  return { workspaces, default_workspace_id };
}

export async function createWorkspace(
  name: string,
  makeDefault = false
): Promise<Workspace> {
  const res = await fetch(`${API_BASE}/workspaces`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ name, make_default: makeDefault }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to create workspace");
  }
  const data = await res.json();
  const ws = data.workspace as Workspace;
  if (makeDefault || ws.is_default) {
    setActiveWorkspaceId(ws.id);
  }
  return ws;
}

export async function switchWorkspace(workspaceId: string): Promise<Workspace> {
  const res = await fetch(`${API_BASE}/workspaces/switch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || "Failed to switch workspace");
  }
  const data = await res.json();
  const ws = data.workspace as Workspace;
  setActiveWorkspaceId(ws.id);
  return ws;
}
