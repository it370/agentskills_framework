"use client";

import { useEffect, useMemo, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  setActiveWorkspace,
  setWorkspaceError,
  setWorkspaceList,
  setWorkspaceLoading,
  upsertWorkspace,
} from "@/store/slices/workspaceSlice";
import { clearAllRuns } from "@/store/slices/runSlice";
import { clearAllLogs } from "@/store/slices/logsSlice";
import {
  createWorkspace as apiCreateWorkspace,
  fetchWorkspaces,
  switchWorkspace as apiSwitchWorkspace,
  Workspace,
} from "@/lib/workspaces";
import { setActiveWorkspaceId } from "@/lib/workspaceStorage";

export default function WorkspaceSwitcher() {
  const dispatch = useAppDispatch();
  const { activeWorkspaceId, workspaces, loading, error, defaultWorkspaceId } =
    useAppSelector((state) => state.workspace);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const activeWorkspace = useMemo(
    () => workspaces.find((w) => w.id === activeWorkspaceId) || null,
    [workspaces, activeWorkspaceId]
  );

  useEffect(() => {
    const load = async () => {
      dispatch(setWorkspaceLoading(true));
      try {
        const data = await fetchWorkspaces();
        dispatch(
          setWorkspaceList({
            workspaces: data.workspaces,
            defaultWorkspaceId: data.default_workspace_id,
          })
        );
        if (!activeWorkspaceId && data.default_workspace_id) {
          dispatch(setActiveWorkspace(data.default_workspace_id));
          setActiveWorkspaceId(data.default_workspace_id);
        }
        dispatch(setWorkspaceError(null));
      } catch (err: any) {
        dispatch(setWorkspaceError(err.message));
      } finally {
        dispatch(setWorkspaceLoading(false));
      }
    };
    load();
  }, [dispatch, activeWorkspaceId]);

  const handleSwitch = async (workspaceId: string) => {
    setBusy(true);
    try {
      dispatch(clearAllRuns());
      dispatch(clearAllLogs());
      const ws = await apiSwitchWorkspace(workspaceId);
      dispatch(setActiveWorkspace(ws.id));
      dispatch(upsertWorkspace(ws));
      setActiveWorkspaceId(ws.id);
      dispatch(setWorkspaceError(null));
    } catch (err: any) {
      dispatch(setWorkspaceError(err.message));
    } finally {
      setBusy(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      const ws = await apiCreateWorkspace(newName.trim(), true);
      dispatch(clearAllRuns());
      dispatch(clearAllLogs());
      dispatch(upsertWorkspace(ws));
      dispatch(setActiveWorkspace(ws.id));
      setActiveWorkspaceId(ws.id);
      setNewName("");
      setShowCreate(false);
      dispatch(setWorkspaceError(null));
    } catch (err: any) {
      dispatch(setWorkspaceError(err.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <div className="flex flex-col">
        <span className="text-[11px] uppercase tracking-wide text-gray-500">
          Workspace
        </span>
        <div className="flex items-center gap-2">
          <select
            className="border border-gray-200 rounded px-2 py-1 text-sm bg-white min-w-[160px] focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={activeWorkspaceId || defaultWorkspaceId || ""}
            disabled={loading || busy}
            onChange={(e) => handleSwitch(e.target.value)}
          >
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>
                {ws.name} {ws.is_default ? "(default)" : ""}
              </option>
            ))}
          </select>
          <button
            className="text-sm px-2 py-1 border border-gray-200 rounded bg-white hover:bg-gray-100 transition"
            onClick={() => setShowCreate((v) => !v)}
            disabled={busy}
            type="button"
          >
            New
          </button>
        </div>
      </div>
      {showCreate && (
        <div className="flex items-center gap-2">
          <input
            type="text"
            className="border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Workspace name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            disabled={busy}
          />
          <button
            className="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
            onClick={handleCreate}
            disabled={busy || !newName.trim()}
            type="button"
          >
            Create
          </button>
        </div>
      )}
      {error && <span className="text-xs text-red-600">{error}</span>}
      {busy && <span className="text-xs text-gray-500">Updating…</span>}
    </div>
  );
}
