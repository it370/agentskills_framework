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
  const { currentThreadId } = useAppSelector((state) => state.run);
  const logsConnectionRef = useRef<{ disconnect: () => void } | null>(null);
  const adminEventsUnsubscribeRef = useRef<(() => void) | null>(null);

  // Initialize a run (called when starting new run or navigating to thread page)
  const initializeRun = async (
    threadId: string,
    config?: { sop: string; initialData: any; runName?: string; llmModel?: string | null }
  ) => {
    console.log('[RunProvider] Initializing run:', threadId);
    
    // Set as current thread
    dispatch(setCurrentThread(threadId));
    
    // If config provided (new run), set initial metadata
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
      
      // Load historical logs only if run is not active
      const isActive = metadata.status === 'running' || metadata.status === 'pending';
      if (!isActive) {
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
          
          // If completed/error, load historical logs
          if (event.status === 'completed' || event.status === 'error') {
            console.log('[RunProvider] Run completed, loading historical logs');
            fetchThreadLogs(threadId)
              .then((logs) => {
                dispatch(setHistoricalLogs({ thread_id: threadId, logs }));
              })
              .catch((err) => {
                console.error('[RunProvider] Failed to load historical logs:', err);
              });
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

  // Set up logs connection (runs once on mount)
  useEffect(() => {
    console.log('[RunProvider] Setting up logs connection');
    
    const logsConnection = connectLogs((message, threadId) => {
      // Add log to store
      dispatch(addLog({
        thread_id: threadId || 'unknown',
        message,
        level: 'INFO',
      }));
    });
    
    logsConnectionRef.current = logsConnection;
    
    return () => {
      console.log('[RunProvider] Cleaning up logs connection');
      logsConnection.disconnect();
    };
  }, [dispatch]);

  const value: RunContextValue = {
    initializeRun,
    loadHistoricalData,
  };

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
