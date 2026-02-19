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
  llm_model?: string | null;
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
  workspace_id?: string;
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
  event_id?: string;
  parent_event_id?: string;
  phase?: string;
  node_kind?: string;
  step_type?: string;
  execution_mode?: "serial" | "parallel" | "parallel_group";
  agent_name?: string;
  source?: string;
  message?: string;
  reasoning?: string;
  pipeline_id?: string;
  pipeline_step_id?: string;
  parallel_group_id?: string;
  branch_id?: string;
  parallel_branch_index?: number;
  parallel_branch_count?: number;
  inputs?: Record<string, any>;
  outputs?: Record<string, any>;
  consumes_from?: string[];
  rich?: {
    images?: string[];
    urls?: string[];
    json?: any;
    wkt?: string[];
  };
};

export type RunListResponse = { runs: (CheckpointTuple | RunSummary)[] };

