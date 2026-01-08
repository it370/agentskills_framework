"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { connectAdminEvents, fetchRuns } from "../lib/api";
import { CheckpointTuple, RunEvent } from "../lib/types";
import DashboardLayout from "../components/DashboardLayout";

type RunRow = {
  thread_id: string;
  checkpoint_id?: string;
  active_skill?: string | null;
  updated_at?: string;
  history?: string[];
  status?: string;
};

function normalizeRun(cp: CheckpointTuple): RunRow {
  const threadId =
    cp.config?.configurable?.thread_id || cp.metadata?.thread_id || "unknown";
  const history = (cp.checkpoint?.channel_values?.history ||
    cp.checkpoint?.history ||
    []) as string[];
  const active =
    cp.checkpoint?.channel_values?.active_skill ||
    cp.checkpoint?.active_skill ||
    null;
  const updated = cp.metadata?.ts || cp.metadata?.updated_at;

  // Debug: log the checkpoint to understand structure
  console.log("Normalizing run:", { threadId, active, historyLength: history.length, checkpoint: cp.checkpoint });

  // Derive status from active_skill and history
  let status = "pending";
  
  // Check if explicitly marked as END
  if (active === "END") {
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

  console.log("Status determined:", status);

  return {
    thread_id: threadId,
    checkpoint_id: cp.checkpoint?.id,
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
  const [runs, setRuns] = useState<Record<string, RunRow>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const threadId = evt.thread_id; // Capture for type narrowing
      setRuns((prev) => ({
        ...prev,
        [threadId]: {
          ...(prev[threadId] || { thread_id: threadId }),
          checkpoint_id: evt.checkpoint_id || prev[threadId]?.checkpoint_id,
          updated_at: evt.metadata?.ts || prev[threadId]?.updated_at,
          active_skill:
            evt.metadata?.active_skill || prev[threadId]?.active_skill,
          status: prev[threadId]?.status || "running",
        },
      }));
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
                <span className="text-xs font-medium text-gray-600">Completed</span>
                <span className="text-lg font-bold text-emerald-600">
                  {orderedRuns.filter((r) => r.status === "completed").length}
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
              <Link
                key={run.thread_id}
                href={`/admin/${run.thread_id}`}
                className="block group"
              >
                <div className="bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-lg transition-all duration-150">
                  <div className="p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        {/* Status Indicator */}
                        <div className="flex-shrink-0">
                          <StatusBadge status={run.status} />
                        </div>

                        {/* Thread ID */}
                        <div className="flex-1 min-w-0">
                          <h3 className="text-base font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
                            {run.thread_id}
                          </h3>
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
              </Link>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
