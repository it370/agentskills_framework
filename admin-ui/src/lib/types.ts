export type CheckpointTuple = {
  config: Record<string, any>;
  checkpoint: Record<string, any>;
  metadata: Record<string, any>;
  parent_config?: Record<string, any> | null;
  pending_writes?: any[] | null;
};

export type RunSummary = {
  thread_id: string;
  run_name?: string;
  sop?: string;
  initial_data?: Record<string, any>;
  parent_thread_id?: string;
  rerun_count?: number;
  status?: string;
  created_at?: string;
  updated_at?: string;
  sop_preview?: string;
  error_message?: string;
  failed_skill?: string;
  user_id?: string | number;
  completed_at?: string;
};

export type RunEvent = {
  type?: string;  // Event type: 'ack', 'run_started', 'status_updated', etc.
  thread_id?: string;
  checkpoint_id?: string;
  checkpoint_ns?: string;
  metadata?: Record<string, any>;
  status?: string;  // For status_updated events
  run_name?: string;  // For ack and run_started events
  event?: string;  // Legacy field name (some events use 'event' instead of 'type')
};

export type RunListResponse = { runs: (CheckpointTuple | RunSummary)[] };

