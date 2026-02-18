"use client";

import React, { createContext, useContext, useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import type { RunMetadata } from '../store/slices/runSlice';
import {
  setCurrentThread,
  setRunMetadata,
  setRunCheckpoint,
  setRunStatus,
  addEvent,
} from '../store/slices/runSlice';
import {
  addLog,
  setHistoricalLogs,
  markHistoricalLogsLoaded,
} from '../store/slices/logsSlice';
import { adminEvents } from '../lib/adminEvents';
import { connectLogs, getRunMetadata, fetchRunDetail, fetchThreadLogs } from '../lib/api';
import { store } from '../store';

interface RunContextValue {
  // Methods to interact with runs
  initializeRun: (threadId: string, config?: { sop: string; initialData: any; runName?: string; llmModel?: string | null }) => Promise<void>;
  loadHistoricalData: (threadId: string) => Promise<void>;
}

const RunContext = createContext<RunContextValue | null>(null);

export const useRun = () => {
  const context = useContext(RunContext);
  if (!context) {
    throw new Error('useRun must be used within RunProvider');
  }
  return context;
};

export function RunProvider({ children }: { children: React.ReactNode }) {
  const dispatch = useAppDispatch();
  const logsConnectionRef = useRef<{ disconnect: () => void } | null>(null);
  const adminEventsUnsubscribeRef = useRef<(() => void) | null>(null);

  // Initialize a run (called when starting new run or navigating to thread page)
  const initializeRun = async (
    threadId: string,
    config?: { sop: string; initialData: any; runName?: string; llmModel?: string | null }
  ) => {
    console.log('[RunProvider] Initializing run:', threadId);
    dispatch(setCurrentThread(threadId));
    if (config) {
      dispatch(setRunMetadata({
        threadId,
        metadata: {
          thread_id: threadId,
          run_name: config.runName || threadId,
          sop: config.sop,
          initial_data: config.initialData,
          llm_model: config.llmModel || null,
          status: 'pending',
          created_at: new Date().toISOString(),
        },
      }));
    }
  };

  // Load historical data for a thread (metadata, checkpoint, logs)
  const loadHistoricalData = async (threadId: string) => {
    console.log('[RunProvider] Loading historical data for:', threadId);
    
    try {
      // Load metadata
      const metadata = await getRunMetadata(threadId);
      const normalizedMetadata = {
        ...metadata,
        run_name: metadata.run_name || threadId,
        status: (metadata.status as RunMetadata['status']) || 'pending',
      };
      dispatch(setRunMetadata({ threadId, metadata: normalizedMetadata }));
      
      // Load checkpoint if available
      try {
        const checkpoint = await fetchRunDetail(threadId);
        dispatch(setRunCheckpoint({ threadId, checkpoint }));
      } catch (err) {
        console.log('[RunProvider] Checkpoint not available yet');
      }
      
      // Load historical logs only for terminal runs (completed/error/cancelled).
      // Active and paused runs receive live logs via SSE — don't replace them with
      // a DB snapshot that may lag behind what the stream has already delivered.
      const isLive = metadata.status === 'running' || metadata.status === 'pending' || metadata.status === 'paused';
      if (!isLive) {
        const logs = await fetchThreadLogs(threadId);
        dispatch(setHistoricalLogs({ thread_id: threadId, logs }));
      } else {
        dispatch(markHistoricalLogsLoaded(threadId));
      }
    } catch (err) {
      console.error('[RunProvider] Failed to load historical data:', err);
      throw err;
    }
  };

  // Set up global event listeners (runs once on mount)
  useEffect(() => {
    console.log('[RunProvider] Setting up global event listeners');
    
    // Subscribe to all admin events
    const unsubscribe = adminEvents.on('*', (event: any) => {
      const eventType = event.type || event.event || 'unknown';
      const threadId = event.thread_id;
      
      console.log('[RunProvider] Event received:', eventType, 'for thread:', threadId);
      
      // Track event
      dispatch(addEvent({
        type: eventType,
        thread_id: threadId,
        data: event,
      }));
      
      // Handle specific events
      switch (eventType) {
        case 'ack':
          // ACK received - run has been accepted by server
          dispatch(setRunMetadata({
            threadId,
            metadata: {
              thread_id: threadId,
              run_name: event.run_name || threadId,
              sop: '',
              initial_data: {},
              status: 'pending',
            },
          }));
          break;
          
        case 'run_started':
          // Run has started
          dispatch(setRunStatus({ threadId, status: 'running' }));
          break;
          
        case 'status_updated':
          // Status changed
          if (event.status) {
            dispatch(setRunStatus({ threadId, status: event.status }));
          }
          
          if (event.status === 'completed' || event.status === 'error') {
            // Only replace logs with DB copy when there are NO live SSE logs in the
            // store for this thread. If logs are already present they came from the
            // active SSE stream and are already complete (and more up-to-date than
            // the DB, which may still be catching up from the Redis flush).
            const existingLogs = (store.getState() as any).logs?.logsByThread?.[threadId];
            const hasLiveLogs = existingLogs && existingLogs.length > 0;
            if (!hasLiveLogs) {
              console.log('[RunProvider] Run completed, no live logs – fetching from DB');
              fetchThreadLogs(threadId)
                .then((logs) => {
                  dispatch(setHistoricalLogs({ thread_id: threadId, logs }));
                })
                .catch((err) => {
                  console.error('[RunProvider] Failed to load historical logs:', err);
                });
            } else {
              console.log(`[RunProvider] Run completed, keeping ${existingLogs.length} live SSE logs`);
              // Mark as loaded so the "loading" spinner doesn't persist
              dispatch(markHistoricalLogsLoaded(threadId));
            }
          }
          break;
          
        case 'checkpoint_saved':
          // Checkpoint saved - reload checkpoint data
          fetchRunDetail(threadId)
            .then((checkpoint) => {
              dispatch(setRunCheckpoint({ threadId, checkpoint }));
            })
            .catch((err) => {
              console.error('[RunProvider] Failed to load checkpoint:', err);
            });
          break;
      }
    });
    
    adminEventsUnsubscribeRef.current = unsubscribe;
    
    return () => {
      console.log('[RunProvider] Cleaning up admin events listener');
      unsubscribe();
    };
  }, [dispatch]);

  // Global SSE logs connection (/api/logs/stream)
  useEffect(() => {
    const logsConnection = connectLogs((message, threadId) => {
      dispatch(addLog({
        thread_id: threadId || 'unknown',
        message,
        level: 'INFO',
      }));
    });
    logsConnectionRef.current = logsConnection;
    return () => logsConnection.disconnect();
  }, [dispatch]);

  const value: RunContextValue = {
    initializeRun,
    loadHistoricalData,
  };

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
