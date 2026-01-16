import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { Workspace } from "@/lib/workspaces";
import { getActiveWorkspaceId } from "@/lib/workspaceStorage";

export interface WorkspaceState {
  activeWorkspaceId: string | null;
  defaultWorkspaceId: string | null;
  workspaces: Workspace[];
  loading: boolean;
  error: string | null;
}

const initialState: WorkspaceState = {
  activeWorkspaceId: getActiveWorkspaceId(),
  defaultWorkspaceId: null,
  workspaces: [],
  loading: false,
  error: null,
};

const workspaceSlice = createSlice({
  name: "workspace",
  initialState,
  reducers: {
    setWorkspaceLoading(state, action: PayloadAction<boolean>) {
      state.loading = action.payload;
    },
    setWorkspaceError(state, action: PayloadAction<string | null>) {
      state.error = action.payload;
    },
    setActiveWorkspace(state, action: PayloadAction<string | null>) {
      state.activeWorkspaceId = action.payload;
    },
    setWorkspaceList(
      state,
      action: PayloadAction<{ workspaces: Workspace[]; defaultWorkspaceId?: string | null }>
    ) {
      state.workspaces = action.payload.workspaces;
      state.defaultWorkspaceId = action.payload.defaultWorkspaceId || null;
      if (!state.activeWorkspaceId && action.payload.defaultWorkspaceId) {
        state.activeWorkspaceId = action.payload.defaultWorkspaceId;
      }
    },
    upsertWorkspace(state, action: PayloadAction<Workspace>) {
      const idx = state.workspaces.findIndex((w) => w.id === action.payload.id);
      if (idx >= 0) {
        state.workspaces[idx] = action.payload;
      } else {
        state.workspaces.push(action.payload);
      }
    },
  },
});

export const {
  setWorkspaceLoading,
  setWorkspaceError,
  setActiveWorkspace,
  setWorkspaceList,
  upsertWorkspace,
} = workspaceSlice.actions;

export default workspaceSlice.reducer;
