import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface LogEntry {
  id: string;
  thread_id: string;
  message: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
  timestamp: number;
  persisted?: boolean; // Whether log was loaded from DB vs. live
}

export interface LogsState {
  // Logs indexed by thread_id
  logsByThread: Record<string, LogEntry[]>;
  
  // Historical logs loading state
  historicalLogsLoaded: Record<string, boolean>;
  
  // Max logs to keep per thread
  maxLogsPerThread: number;
}

const initialState: LogsState = {
  logsByThread: {},
  historicalLogsLoaded: {},
  maxLogsPerThread: 1000,
};

const logsSlice = createSlice({
  name: 'logs',
  initialState,
  reducers: {
    // Add a single log entry (live log)
    addLog(state, action: PayloadAction<{ thread_id: string; message: string; level?: LogEntry['level'] }>) {
      const { thread_id, message, level = 'INFO' } = action.payload;
      
      if (!state.logsByThread[thread_id]) {
        state.logsByThread[thread_id] = [];
      }
      
      const logEntry: LogEntry = {
        id: `${thread_id}-${Date.now()}-${Math.random()}`,
        thread_id,
        message,
        level,
        timestamp: Date.now(),
        persisted: false,
      };
      
      // Add and trim to max logs
      state.logsByThread[thread_id] = [
        ...state.logsByThread[thread_id].slice(-(state.maxLogsPerThread - 1)),
        logEntry,
      ];
    },
    
    // Set historical logs (from database)
    setHistoricalLogs(state, action: PayloadAction<{ thread_id: string; logs: Array<{message: string; level?: string; created_at: string}> }>) {
      const { thread_id, logs } = action.payload;
      
      const historicalLogs: LogEntry[] = logs.map((log, index) => ({
        id: `${thread_id}-historical-${index}`,
        thread_id,
        message: log.message,
        level: (log.level as LogEntry['level']) || 'INFO',
        timestamp: new Date(log.created_at).getTime(),
        persisted: true,
      }));
      
      // Replace all logs with historical logs
      state.logsByThread[thread_id] = historicalLogs;
      state.historicalLogsLoaded[thread_id] = true;
    },
    
    // Add multiple logs (bulk)
    addLogsBulk(state, action: PayloadAction<{ thread_id: string; logs: Array<{message: string; level?: LogEntry['level']}> }>) {
      const { thread_id, logs } = action.payload;
      
      if (!state.logsByThread[thread_id]) {
        state.logsByThread[thread_id] = [];
      }
      
      const newLogs: LogEntry[] = logs.map((log, index) => ({
        id: `${thread_id}-${Date.now()}-${index}`,
        thread_id,
        message: log.message,
        level: log.level || 'INFO',
        timestamp: Date.now() + index, // Slight offset for ordering
        persisted: false,
      }));
      
      // Add and trim to max logs
      state.logsByThread[thread_id] = [
        ...state.logsByThread[thread_id],
        ...newLogs,
      ].slice(-state.maxLogsPerThread);
    },
    
    // Mark historical logs as loaded
    markHistoricalLogsLoaded(state, action: PayloadAction<string>) {
      state.historicalLogsLoaded[action.payload] = true;
    },
    
    // Clear logs for a thread
    clearLogs(state, action: PayloadAction<string>) {
      delete state.logsByThread[action.payload];
      delete state.historicalLogsLoaded[action.payload];
    },
    
    // Clear all logs
    clearAllLogs(state) {
      state.logsByThread = {};
      state.historicalLogsLoaded = {};
    },
  },
});

export const {
  addLog,
  setHistoricalLogs,
  addLogsBulk,
  markHistoricalLogsLoaded,
  clearLogs,
  clearAllLogs,
} = logsSlice.actions;

export default logsSlice.reducer;
