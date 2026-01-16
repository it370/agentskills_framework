import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { CheckpointTuple } from '../../lib/types';

export interface RunMetadata {
  thread_id: string;
  run_name: string;
  sop: string;
  initial_data: any;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'error';
  created_at?: string;
  updated_at?: string;
  user_id?: string;
  parent_thread_id?: string;
  rerun_count?: number;
  workspace_id?: string;
}

export interface RunState {
  // Current active run
  currentThreadId: string | null;
  
  // Run data indexed by thread_id
  runs: Record<string, {
    metadata: RunMetadata | null;
    checkpoint: CheckpointTuple | null;
    loading: boolean;
    error: string | null;
    lastUpdated: number;
  }>;
  
  // Event tracking
  events: Array<{
    id: string;
    type: string;
    thread_id: string;
    data: any;
    timestamp: number;
  }>;
}

const initialState: RunState = {
  currentThreadId: null,
  runs: {},
  events: [],
};

const runSlice = createSlice({
  name: 'run',
  initialState,
  reducers: {
    // Set the current active thread
    setCurrentThread(state, action: PayloadAction<string | null>) {
      state.currentThreadId = action.payload;
      
      // Initialize run data if not exists
      if (action.payload && !state.runs[action.payload]) {
        state.runs[action.payload] = {
          metadata: null,
          checkpoint: null,
          loading: false,
          error: null,
          lastUpdated: Date.now(),
        };
      }
    },
    
    // Update run metadata
    setRunMetadata(state, action: PayloadAction<{ threadId: string; metadata: RunMetadata }>) {
      const { threadId, metadata } = action.payload;
      
      if (!state.runs[threadId]) {
        state.runs[threadId] = {
          metadata: null,
          checkpoint: null,
          loading: false,
          error: null,
          lastUpdated: Date.now(),
        };
      }
      
      state.runs[threadId].metadata = metadata;
      state.runs[threadId].lastUpdated = Date.now();
    },
    
    // Update checkpoint data
    setRunCheckpoint(state, action: PayloadAction<{ threadId: string; checkpoint: CheckpointTuple }>) {
      const { threadId, checkpoint } = action.payload;
      
      if (!state.runs[threadId]) {
        state.runs[threadId] = {
          metadata: null,
          checkpoint: null,
          loading: false,
          error: null,
          lastUpdated: Date.now(),
        };
      }
      
      state.runs[threadId].checkpoint = checkpoint;
      state.runs[threadId].lastUpdated = Date.now();
    },
    
    // Update run status
    setRunStatus(state, action: PayloadAction<{ threadId: string; status: RunMetadata['status'] }>) {
      const { threadId, status } = action.payload;
      
      if (state.runs[threadId]?.metadata) {
        state.runs[threadId].metadata!.status = status;
        state.runs[threadId].lastUpdated = Date.now();
      }
    },
    
    // Set loading state
    setRunLoading(state, action: PayloadAction<{ threadId: string; loading: boolean }>) {
      const { threadId, loading } = action.payload;
      
      if (state.runs[threadId]) {
        state.runs[threadId].loading = loading;
      }
    },
    
    // Set error
    setRunError(state, action: PayloadAction<{ threadId: string; error: string | null }>) {
      const { threadId, error } = action.payload;
      
      if (state.runs[threadId]) {
        state.runs[threadId].error = error;
        state.runs[threadId].loading = false;
      }
    },
    
    // Track an event
    addEvent(state, action: PayloadAction<{ type: string; thread_id: string; data: any }>) {
      const event = {
        id: `${action.payload.thread_id}-${Date.now()}-${Math.random()}`,
        type: action.payload.type,
        thread_id: action.payload.thread_id,
        data: action.payload.data,
        timestamp: Date.now(),
      };
      
      // Keep last 100 events
      state.events = [...state.events.slice(-99), event];
    },
    
    // Clear run data (cleanup)
    clearRun(state, action: PayloadAction<string>) {
      delete state.runs[action.payload];
      
      if (state.currentThreadId === action.payload) {
        state.currentThreadId = null;
      }
    },
    
    // Clear all run data
    clearAllRuns(state) {
      state.runs = {};
      state.currentThreadId = null;
      state.events = [];
    },
  },
});

export const {
  setCurrentThread,
  setRunMetadata,
  setRunCheckpoint,
  setRunStatus,
  setRunLoading,
  setRunError,
  addEvent,
  clearRun,
  clearAllRuns,
} = runSlice.actions;

export default runSlice.reducer;
