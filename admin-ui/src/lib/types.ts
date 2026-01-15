export type CheckpointTuple = {
  config: Record<string, any>;
  checkpoint: Record<string, any>;
  metadata: Record<string, any>;
  parent_config?: Record<string, any> | null;
  pending_writes?: any[] | null;
};

export type RunSummary = {
  thread_id: string;
  checkpoint_id?: string;
  checkpoint_ns?: string;
  metadata?: Record<string, any>;
  checkpoint?: Record<string, any>;
  updated_at?: string;
  // Enriched fields from view
  active_skill?: string;
  history_count?: number;
  status?: string;
  sop_preview?: string;
  run_name?: string;  // Human-friendly name
  error_message?: string;  // Error message if status is error
  failed_skill?: string;  // Skill that failed
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

