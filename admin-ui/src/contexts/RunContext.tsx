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
import { connectLogs, connectThreadAdminEvents, getRunMetadata, fetchRunDetail, fetchThreadLogs } from '../lib/api';
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
  const currentThreadId = useAppSelector((state) => state.run.currentThreadId);
  const logsConnectionRef = useRef<{ disconnect: () => void } | null>(null);

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

  // Subscribe to thread-scoped admin events for the current run only
  useEffect(() => {
    if (!currentThreadId) return;
    console.log('[RunProvider] Subscribing to thread admin events:', currentThreadId);
      
    const connection = connectThreadAdminEvents(currentThreadId, (event: any) => {
      const eventType = event.type || event.event || 'unknown';
      const threadId = event.thread_id || currentThreadId;

      console.log('[RunProvider] Event received:', eventType, 'for thread:', threadId);

      dispatch(addEvent({
        type: eventType,
        thread_id: threadId,
        data: event,
      }));

      switch (eventType) {
        case 'ack':
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
          dispatch(setRunStatus({ threadId, status: 'running' }));
          break;

        case 'status_updated':
          if (event.status) {
            dispatch(setRunStatus({ threadId, status: event.status }));
          }

          if (event.status === 'completed' || event.status === 'error') {
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
              dispatch(markHistoricalLogsLoaded(threadId));
            }
          }
          break;

        case 'checkpoint_saved':
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

    return () => {
      console.log('[RunProvider] Cleaning up thread admin events listener');
      connection.disconnect();
    };
  }, [dispatch, currentThreadId]);

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
