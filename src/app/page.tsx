"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { connectAdminEvents, fetchRuns, rerunWorkflow, getRunMetadata } from "../lib/api";
import { CheckpointTuple, RunEvent, RunSummary } from "../lib/types";
import DashboardLayout from "../components/DashboardLayout";

type RunRow = {
  thread_id: string;
  checkpoint_id?: string;
  active_skill?: string | null;
  updated_at?: string;
  history?: string[];
  status?: string;
  sop_preview?: string;
  run_name?: string;
};

function normalizeRun(cp: CheckpointTuple | RunSummary): RunRow {
  // If the API already provided enriched data with status, use it directly
  if ('status' in cp && cp.status) {
    return {
      thread_id: cp.thread_id,
      checkpoint_id: cp.checkpoint_id,
      active_skill: cp.active_skill || null,
      updated_at: cp.updated_at,
      history: [],  // Not needed when status is pre-computed
      status: cp.status,
      sop_preview: cp.sop_preview,
      run_name: cp.run_name,  // Include run_name from API
    };
  }

  // Fallback to computing status from checkpoint data
  const checkpointData = cp as CheckpointTuple;
  const threadId =
    checkpointData.config?.configurable?.thread_id || checkpointData.metadata?.thread_id || "unknown";
  const history = (checkpointData.checkpoint?.channel_values?.history ||
    checkpointData.checkpoint?.history ||
    []) as string[];
  const active =
    checkpointData.checkpoint?.channel_values?.active_skill ||
    checkpointData.checkpoint?.active_skill ||
    null;
  const updated = checkpointData.metadata?.ts || checkpointData.metadata?.updated_at;
  
  // Check data_store for error status first
  const dataStore = checkpointData.checkpoint?.channel_values?.data_store || 
                    checkpointData.checkpoint?.data_store || {};

  // Derive status from data_store._status, active_skill and history
  let status = "pending";
  
  // PRIORITY 1: Check if explicitly failed in data_store
  if (dataStore._status === "failed") {
    status = "error";
  }
  // PRIORITY 2: Check history for failure markers
  else if (history.some((h) => {
    const lower = h.toLowerCase();
    return lower.includes("workflow failed") || 
           lower.includes("action") && lower.includes("failed");
  })) {
    status = "error";
  }
  // PRIORITY 3: Check if explicitly marked as END
  else if (active === "END") {
    status = "completed";
  } 
  // Check history for completion markers
  else if (history.some((h) => {
    const lower = h.toLowerCase();
    return lower.includes("reached end") || 
           lower.includes("execution completed") || 
           lower.includes("planner chose end");
  })) {
    status = "completed";
  }
  // If actively running a skill
  else if (active && active !== "END" && active !== null) {
    status = "running";
  }
  // If there's history but no active skill, likely completed
  else if (history.length > 0 && !active) {
    status = "completed";
  }

  return {
    thread_id: threadId,
    checkpoint_id: checkpointData.checkpoint?.id,
    active_skill: active,
    updated_at: updated,
    history,
    status,
  };
}

function StatusBadge({ status }: { status?: string }) {
  const config = {
    completed: {
      bg: "bg-emerald-100",
      text: "text-emerald-800",
      dot: "bg-emerald-500",
      label: "Completed",
    },
    running: {
      bg: "bg-blue-100",
      text: "text-blue-800",
      dot: "bg-blue-500 animate-pulse",
      label: "Running",
    },
    paused: {
      bg: "bg-amber-100",
      text: "text-amber-800",
      dot: "bg-amber-500 animate-pulse",
      label: "Awaiting Review",
    },
    error: {
      bg: "bg-red-100",
      text: "text-red-800",
      dot: "bg-red-500",
      label: "Error",
    },
    pending: {
      bg: "bg-gray-100",
      text: "text-gray-700",
      dot: "bg-gray-400",
      label: "Pending",
    },
  };

  const c = config[status as keyof typeof config] || config.pending;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${c.bg} ${c.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`}></span>
      {c.label}
    </span>
  );
}

function formatRelativeTime(timestamp?: string): string {
  if (!timestamp) return "—";
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return `${diffSecs}s ago`;
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "1d ago";
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  } catch {
    return timestamp;
  }
}

export default function RunsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<Record<string, RunRow>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rerunningThreadId, setRerunningThreadId] = useState<string | null>(null);
  const [openMenuThreadId, setOpenMenuThreadId] = useState<string | null>(null);

  const handleRerunAsIs = async (threadId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setOpenMenuThreadId(null); // Close menu
    
    if (!confirm(`Rerun workflow with same inputs?`)) {
      return;
    }
    
    setRerunningThreadId(threadId);
    try {
      const result = await rerunWorkflow(threadId);
      console.log("[Rerun] Success:", result);
      
      // Navigate to the new thread
      router.push(`/admin/${result.thread_id}`);
    } catch (err: any) {
      console.error("[Rerun] Error:", err);
      alert(`Failed to rerun: ${err.message}`);
    } finally {
      setRerunningThreadId(null);
    }
  };

  const handleEditAndRerun = async (threadId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setOpenMenuThreadId(null); // Close menu
    
    try {
      // Fetch the run metadata
      const metadata = await getRunMetadata(threadId);
      
      // Navigate to new run page with pre-populated data
      const params = new URLSearchParams({
        runName: metadata.run_name || '',
        sop: metadata.sop,
        initialData: JSON.stringify(metadata.initial_data, null, 2)
      });
      
      router.push(`/runs/new?${params.toString()}`);
    } catch (err: any) {
      console.error("[EditRerun] Error:", err);
      alert(`Failed to load run data: ${err.message}`);
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchRuns()
      .then((data) => {
        if (cancelled) return;
        const next: Record<string, RunRow> = {};
        data.forEach((cp) => {
          const row = normalizeRun(cp);
          next[row.thread_id] = row;
        });
        setRuns(next);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const ws = connectAdminEvents((evt: RunEvent) => {
      if (!evt.thread_id) return;
      const threadId = evt.thread_id;
      
      // Refetch the run data from API to get latest status from view
      fetchRuns().then((data) => {
        const updatedRun = data.find((cp) => {
          const cpThreadId = 'thread_id' in cp ? cp.thread_id : 
                            cp.config?.configurable?.thread_id || 
                            cp.metadata?.thread_id;
          return cpThreadId === threadId;
        });
        
        if (updatedRun) {
          setRuns((prev) => ({
            ...prev,
            [threadId]: normalizeRun(updatedRun),
          }));
        } else {
          // Fallback to update from event if not found in list
          setRuns((prev) => ({
            ...prev,
            [threadId]: {
              ...(prev[threadId] || { thread_id: threadId }),
              checkpoint_id: evt.checkpoint_id || prev[threadId]?.checkpoint_id,
              updated_at: evt.metadata?.ts || prev[threadId]?.updated_at,
              active_skill: evt.metadata?.active_skill || prev[threadId]?.active_skill,
              status: prev[threadId]?.status || "running",
            },
          }));
        }
      }).catch(err => {
        console.error("[Runs] Failed to refetch after event:", err);
        // Fallback to basic update
        setRuns((prev) => ({
          ...prev,
          [threadId]: {
            ...(prev[threadId] || { thread_id: threadId }),
            checkpoint_id: evt.checkpoint_id || prev[threadId]?.checkpoint_id,
            updated_at: evt.metadata?.ts || prev[threadId]?.updated_at,
            active_skill: evt.metadata?.active_skill || prev[threadId]?.active_skill,
            status: prev[threadId]?.status || "running",
          },
        }));
      });
    });
    return () => ws.close();
  }, []);

  const orderedRuns = useMemo(
    () =>
      Object.values(runs).sort(
        (a, b) => (b.updated_at || "").localeCompare(a.updated_at || "")
      ),
    [runs]
  );

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Workflow Runs</h1>
              <p className="mt-1 text-sm text-gray-600">
                Real-time monitoring of workflow executions
              </p>
            </div>
            <Link
              href="/runs/new"
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Run
            </Link>
          </div>
          <div className="mt-4 flex items-center justify-end">

            {/* Compact Stats */}
            <div className="flex items-center gap-6 bg-white rounded-lg border border-gray-200 px-6 py-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-600">Total</span>
                <span className="text-lg font-bold text-gray-900">{orderedRuns.length}</span>
              </div>
              <div className="w-px h-8 bg-gray-200"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-600">Running</span>
                <span className="text-lg font-bold text-blue-600">
                  {orderedRuns.filter((r) => r.status === "running").length}
                </span>
              </div>
              <div className="w-px h-8 bg-gray-200"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-600">Paused</span>
                <span className="text-lg font-bold text-amber-600">
                  {orderedRuns.filter((r) => r.status === "paused").length}
                </span>
              </div>
              <div className="w-px h-8 bg-gray-200"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-600">Completed</span>
                <span className="text-lg font-bold text-emerald-600">
                  {orderedRuns.filter((r) => r.status === "completed").length}
                </span>
              </div>
              <div className="w-px h-8 bg-gray-200"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-600">Error</span>
                <span className="text-lg font-bold text-red-600">
                  {orderedRuns.filter((r) => r.status === "error").length}
                </span>
              </div>
              <div className="w-px h-8 bg-gray-200"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-600">Pending</span>
                <span className="text-lg font-bold text-gray-600">
                  {orderedRuns.filter((r) => r.status === "pending").length}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4 flex items-start gap-3">
            <svg
              className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <h3 className="text-sm font-medium text-red-800">
                Failed to load runs
              </h3>
              <p className="mt-1 text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Runs List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-4">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-gray-900"></div>
              <p className="text-sm text-gray-600">Loading runs...</p>
            </div>
          </div>
        ) : orderedRuns.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
            <h3 className="mt-4 text-base font-semibold text-gray-900">
              No runs yet
            </h3>
            <p className="mt-1 text-sm text-gray-600">
              Start a workflow execution to see it here
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {orderedRuns.map((run) => (
              <div
                key={run.thread_id}
                className="bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-lg transition-all duration-150"
              >
                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/admin/${run.thread_id}`}
                      className="flex items-center gap-4 flex-1 min-w-0 group"
                    >
                      {/* Status Indicator */}
                      <div className="flex-shrink-0">
                        <StatusBadge status={run.status} />
                      </div>

                      {/* Thread ID / Run Name */}
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
                          {run.run_name || run.thread_id}
                        </h3>
                        {run.run_name && run.run_name !== run.thread_id && (
                          <p className="text-xs text-gray-500 truncate mt-0.5">
                            {run.thread_id}
                          </p>
                        )}
                      </div>

                      {/* Metadata */}
                      <div className="flex items-center gap-6 text-sm text-gray-600">
                        {run.active_skill && run.active_skill !== "END" && (
                          <div className="flex items-center gap-2">
                            <svg
                              className="w-4 h-4 text-gray-400"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M13 10V3L4 14h7v7l9-11h-7z"
                              />
                            </svg>
                            <span className="font-medium">
                              {run.active_skill}
                            </span>
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          <svg
                            className="w-4 h-4 text-gray-400"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          <span>{formatRelativeTime(run.updated_at)}</span>
                        </div>
                        {run.history && run.history.length > 0 && (
                          <div className="flex items-center gap-2">
                            <svg
                              className="w-4 h-4 text-gray-400"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                              />
                            </svg>
                            <span>{run.history.length} steps</span>
                          </div>
                        )}
                      </div>

                      {/* Arrow */}
                      <svg
                        className="w-5 h-5 text-gray-400 group-hover:text-gray-600 flex-shrink-0 transition-colors"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </Link>

                    {/* Rerun Menu */}
                    <div className="ml-4 relative">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setOpenMenuThreadId(openMenuThreadId === run.thread_id ? null : run.thread_id);
                        }}
                        className="p-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
                        title="Rerun options"
                      >
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
                          />
                        </svg>
                      </button>

                      {/* Dropdown Menu */}
                      {openMenuThreadId === run.thread_id && (
                        <>
                          {/* Backdrop to close menu */}
                          <div
                            className="fixed inset-0 z-10"
                            onClick={() => setOpenMenuThreadId(null)}
                          />
                          
                          {/* Menu */}
                          <div className="absolute right-0 mt-2 w-56 rounded-lg shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-20">
                            <div className="py-1">
                              <button
                                onClick={(e) => handleRerunAsIs(run.thread_id, e)}
                                disabled={rerunningThreadId === run.thread_id}
                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                              >
                                <svg
                                  className="w-4 h-4"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                                  />
                                </svg>
                                {rerunningThreadId === run.thread_id ? 'Rerunning...' : 'Rerun as is'}
                              </button>
                              
                              <button
                                onClick={(e) => handleEditAndRerun(run.thread_id, e)}
                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                              >
                                <svg
                                  className="w-4 h-4"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                  />
                                </svg>
                                Edit and rerun
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Last History Entry */}
                  {run.history && run.history.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-sm text-gray-600 truncate">
                        <span className="font-medium text-gray-700">
                          Latest:
                        </span>{" "}
                        {run.history[run.history.length - 1]}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
