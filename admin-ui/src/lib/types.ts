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
};

export type RunEvent = {
  thread_id?: string;
  checkpoint_id?: string;
  checkpoint_ns?: string;
  metadata?: Record<string, any>;
};

export type RunListResponse = { runs: CheckpointTuple[] };

