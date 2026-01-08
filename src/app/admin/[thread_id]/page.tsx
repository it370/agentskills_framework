"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { connectAdminEvents, connectLogs, fetchRunDetail, fetchThreadLogs, approveStep } from "../../../lib/api";
import { CheckpointTuple, RunEvent } from "../../../lib/types";
import DashboardLayout from "../../../components/DashboardLayout";

export default function RunDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const threadId = params?.thread_id as string;
  const [run, setRun] = useState<CheckpointTuple | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>(searchParams.get("tab") || "config");
  const [logs, setLogs] = useState<Array<{id: number, text: string, timestamp: Date, threadId?: string}>>([]);
  const [historicalLogsLoaded, setHistoricalLogsLoaded] = useState(false);
  const [showHitlModal, setShowHitlModal] = useState(false);
  const [hitlData, setHitlData] = useState<string>("");
  const [approving, setApproving] = useState(false);
  const logIdCounter = useRef(0);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const hasCheckedInitialState = useRef(false);

  // Get config from URL params if starting from new run
  const sopFromUrl = searchParams.get("sop");
  const initialDataFromUrl = searchParams.get("initialData");
  
  // Parse and store initial config on mount (only once)
  const [initialConfig, setInitialConfig] = useState<{sop: string, data: any} | null>(null);
  
  useEffect(() => {
    if (sopFromUrl && initialDataFromUrl && !initialConfig) {
      try {
        setInitialConfig({
          sop: sopFromUrl,
          data: JSON.parse(initialDataFromUrl)
        });
      } catch (e) {
        console.error("Failed to parse initial data from URL", e);
      }
    }
  }, [sopFromUrl, initialDataFromUrl, initialConfig]);

  const load = () => {
    setLoading(true);
    fetchRunDetail(threadId)
      .then((data) => {
        setRun(data);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!threadId) return;
    load();
    const ws = connectAdminEvents((evt: RunEvent) => {
      if (evt.thread_id === threadId) {
        load();
      }
    });
    return () => ws.close();
  }, [threadId]);

  // Load historical logs from database on mount
  useEffect(() => {
    if (!threadId || historicalLogsLoaded) return;
    
    console.log("[RunDetail] Loading historical logs for thread:", threadId);
    fetchThreadLogs(threadId)
      .then((historicalLogs) => {
        console.log("[RunDetail] Loaded", historicalLogs.length, "historical logs");
        // Convert historical logs to the same format as live logs
        const convertedLogs = historicalLogs.map((log) => ({
          id: logIdCounter.current++,
          text: log.message,
          timestamp: new Date(log.created_at),
          threadId: log.thread_id
        }));
        setLogs(convertedLogs);
        setHistoricalLogsLoaded(true);
      })
      .catch((err) => {
        console.error("[RunDetail] Failed to load historical logs:", err);
        setHistoricalLogsLoaded(true); // Mark as loaded even on error to avoid retries
      });
  }, [threadId, historicalLogsLoaded]);

  // Live logs WebSocket connection
  useEffect(() => {
    console.log("[RunDetail] Setting up logs connection for thread:", threadId);
    const ws = connectLogs((line, logThreadId) => {
      console.log("[RunDetail] Log line received:", line, "thread_id:", logThreadId);
      setLogs((prev) => {
        const newLog = { 
          id: logIdCounter.current++, 
          text: line, 
          timestamp: new Date(),
          threadId: logThreadId
        };
        // Keep last 1000 logs
        return [...prev.slice(-999), newLog];
      });
    });
    return () => {
      console.log("[RunDetail] Closing logs connection");
      ws.close();
    };
  }, []);

  const history =
    (run?.checkpoint?.channel_values?.history ||
      run?.checkpoint?.history ||
      []) as string[];

  const activeSkill = run?.checkpoint?.channel_values?.active_skill ||
    run?.checkpoint?.active_skill;

  const dataStore = run?.checkpoint?.channel_values?.data_store || run?.checkpoint?.data_store || {};
  
  // Check if we're at a human review interrupt (most reliable)
  const isAtHumanReview = run?.checkpoint?.channel_values?.["branch:to:human_review"] !== undefined ||
                          run?.checkpoint?.["branch:to:human_review"] !== undefined;
  
  // Extract layman_sop from checkpoint if available, otherwise use URL param or stored initial config
  const laymanSop = run?.checkpoint?.channel_values?.layman_sop || 
                    initialConfig?.sop || 
                    sopFromUrl || 
                    "—";
  
  // For initial data, prefer stored initial config, then URL param, then empty
  const initialData = initialConfig?.data || 
                     (initialDataFromUrl ? (() => { try { return JSON.parse(initialDataFromUrl); } catch { return {}; } })() : {});

  // Filter logs for this specific thread
  const threadLogs = logs.filter((logEntry) => {
    // First, check if we have explicit thread_id metadata from the backend
    if (logEntry.threadId) {
      return logEntry.threadId === threadId;
    }
    
    // Fallback: check if thread_id appears in the log text (for backward compatibility)
    const logText = logEntry.text;
    const lowerLog = logText.toLowerCase();
    const lowerThreadId = threadId.toLowerCase();
    
    // Extract UUID part if thread_id has "thread_" prefix
    const uuidPart = threadId.startsWith("thread_") 
      ? threadId.substring(7).toLowerCase() 
      : null;
    
    // Match various formats:
    // 1. Direct inclusion anywhere in the log
    if (lowerLog.includes(lowerThreadId)) return true;
    
    // 2. UUID part match (if applicable)
    if (uuidPart && lowerLog.includes(uuidPart)) return true;
    
    return false;
  });

  // Debug: log filtering results
  useEffect(() => {
    console.log(`[RunDetail] Thread: ${threadId}, Total logs: ${logs.length}, Filtered: ${threadLogs.length}`);
    if (logs.length > 0 && threadLogs.length === 0) {
      console.log("[RunDetail] Sample logs (first 3):", logs.slice(0, 3).map(l => ({ text: l.text, threadId: l.threadId })));
    }
  }, [logs.length, threadLogs.length, threadId, logs]);

  const status: "pending" | "running" | "paused" | "completed" = 
    activeSkill === "END" ? "completed" :
    // Check explicit human review state first (most reliable)
    isAtHumanReview ? "paused" :
    activeSkill && activeSkill !== "END" ? "running" : 
    // Fallback: check history for HITL markers
    history.some(h => h.toLowerCase().includes("awaiting human review") || 
                      h.toLowerCase().includes("redirecting to human_review") ||
                      h.toLowerCase().includes("hitl enabled")) ? "paused" :
    history.length > 0 ? "completed" :
    "pending";

  // Debug status detection
  useEffect(() => {
    console.log("[RunDetail] Status detection:", {
      status,
      activeSkill,
      isAtHumanReview,
      historyLength: history.length,
      lastHistory: history[history.length - 1],
      branchValue: run?.checkpoint?.channel_values?.["branch:to:human_review"]
    });
  }, [status, activeSkill, history, isAtHumanReview, run]);

  const getStatusConfig = () => {
    switch (status) {
      case "completed":
        return { bg: "bg-emerald-100", text: "text-emerald-800", dot: "bg-emerald-500" };
      case "running":
        return { bg: "bg-blue-100", text: "text-blue-800", dot: "bg-blue-500 animate-pulse" };
      case "paused":
        return { bg: "bg-amber-100", text: "text-amber-800", dot: "bg-amber-500 animate-pulse" };
      default:
        return { bg: "bg-gray-100", text: "text-gray-700", dot: "bg-gray-400" };
    }
  };

  const statusConfig = getStatusConfig();

  // Auto-scroll logs when new logs arrive for this thread
  useEffect(() => {
    if (activeTab === "logs" && logContainerRef.current && threadLogs.length > 0) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [threadLogs.length, activeTab]);

  // Check if workflow is paused and waiting for human review
  const isPaused = status === "paused";
  const lastHistoryEntry = history[history.length - 1] || "";
  const awaitingSkill = lastHistoryEntry.match(/Awaiting human review for (.+)/i)?.[1] || 
                       lastHistoryEntry.match(/HITL enabled for (.+)\./i)?.[1] || 
                       activeSkill || "Unknown";

  // Debug HITL state
  useEffect(() => {
    console.log("[RunDetail] HITL state:", {
      isPaused,
      showHitlModal,
      awaitingSkill,
      hasCheckedInitialState: hasCheckedInitialState.current,
      loading
    });
  }, [isPaused, showHitlModal, awaitingSkill, loading]);

  // Update HITL data when dataStore changes
  useEffect(() => {
    if (isPaused) {
      setHitlData(JSON.stringify(dataStore, null, 2));
      
      // Auto-open modal on initial mount if paused
      if (!hasCheckedInitialState.current && !loading) {
        hasCheckedInitialState.current = true;
        setShowHitlModal(true);
      }
    }
  }, [isPaused, dataStore, loading]);

  const handleApprove = async (withChanges: boolean) => {
    setApproving(true);
    try {
      let updatedData = undefined;
      if (withChanges) {
        updatedData = JSON.parse(hitlData);
      }
      await approveStep(threadId, updatedData);
      setShowHitlModal(false);
      // Reload the run data
      setTimeout(() => load(), 500);
    } catch (err: any) {
      setError(err.message || "Failed to approve step");
    } finally {
      setApproving(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Runs
          </Link>
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <h1 className="text-3xl font-bold text-gray-900 truncate">{threadId}</h1>
              <div className="flex items-center gap-4 mt-3">
                <span
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${statusConfig.bg} ${statusConfig.text}`}
                >
                  <span className={`w-2 h-2 rounded-full ${statusConfig.dot}`}></span>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </span>
                {isPaused && (
                  <button
                    onClick={() => setShowHitlModal(true)}
                    className="inline-flex items-center gap-2 px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-full transition-colors animate-pulse"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    Review Required
                  </button>
                )}
                {activeSkill && activeSkill !== "END" && (
                  <span className="text-sm text-gray-600">
                    <span className="font-medium">Active:</span> {activeSkill}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isPaused && (
                <button
                  onClick={() => setShowHitlModal(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white border border-red-700 rounded-lg transition-colors shadow-lg"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  HITL Review
                </button>
              )}
              <button
                onClick={load}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <svg
                  className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
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
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Error */}
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
              <h3 className="text-sm font-medium text-red-800">Failed to load run details</h3>
              <p className="mt-1 text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="flex gap-8">
            {[
              { id: "config", label: "Configuration" },
              { id: "overview", label: "Overview" },
              { id: "history", label: "History", badge: history.length },
              { id: "data", label: "Data Store" },
              { id: "logs", label: "Live Logs", badge: threadLogs.length },
              { id: "metadata", label: "Metadata" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300"
                }`}
              >
                {tab.label}
                {tab.badge !== undefined && (
                  <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-700 rounded-full text-xs">
                    {tab.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        {loading && !run ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
          </div>
        ) : (
          <div>
            {activeTab === "config" && (
              <div className="space-y-6">
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Workflow Instructions</h3>
                  <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{laymanSop}</p>
                  </div>
                </div>
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Initial Data</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto text-sm font-mono">
                    {JSON.stringify(initialData, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {activeTab === "overview" && (
              <div className="grid gap-6">
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Summary</h3>
                  <dl className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="text-sm font-medium text-gray-600">Checkpoint ID</dt>
                      <dd className="mt-1 text-sm text-gray-900 font-mono">
                        {run?.checkpoint?.id || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-600">Checkpoint Namespace</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {run?.config?.configurable?.checkpoint_ns || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-600">Updated At</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {run?.metadata?.ts || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-600">History Events</dt>
                      <dd className="mt-1 text-sm text-gray-900">{history.length}</dd>
                    </div>
                  </dl>
                </div>

                {history.length > 0 && (
                  <div className="bg-white rounded-lg border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Latest Activity</h3>
                    <div className="space-y-2">
                      {history.slice(-5).reverse().map((h, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5"></div>
                          <p className="text-sm text-gray-700 flex-1">{h}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "history" && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Execution History</h3>
                {history.length === 0 ? (
                  <p className="text-sm text-gray-600">No history events recorded yet.</p>
                ) : (
                  <div className="space-y-3">
                    {history.map((h, idx) => (
                      <div key={idx} className="flex items-start gap-4 pb-3 border-b border-gray-100 last:border-0">
                        <div className="flex-shrink-0 w-12 text-sm font-mono text-gray-500">
                          #{idx + 1}
                        </div>
                        <p className="text-sm text-gray-900 flex-1">{h}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "data" && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Store</h3>
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto text-sm font-mono">
                  {JSON.stringify(dataStore, null, 2)}
                </pre>
              </div>
            )}

            {activeTab === "logs" && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Live Logs</h3>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-600">
                      {threadLogs.length} event{threadLogs.length !== 1 ? 's' : ''}
                    </span>
                    {!historicalLogsLoaded && (
                      <span className="text-xs text-blue-600 animate-pulse">
                        Loading historical logs...
                      </span>
                    )}
                    {logs.length > threadLogs.length && (
                      <span className="text-xs text-gray-500">
                        ({logs.length} total across all threads)
                      </span>
                    )}
                  </div>
                </div>
                <div
                  ref={logContainerRef}
                  className="bg-gray-900 text-white p-4 rounded-lg overflow-auto font-mono text-sm"
                  style={{ height: "600px" }}
                >
                  {threadLogs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
                      <div>
                        {historicalLogsLoaded ? "No logs for this thread yet..." : "Loading logs..."}
                      </div>
                      <div className="text-xs">Waiting for events from: {threadId}</div>
                      {logs.length > 0 && (
                        <div className="text-xs mt-2">
                          ({logs.length} log{logs.length !== 1 ? 's' : ''} received from other threads)
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {threadLogs.map((logEntry) => {
                        // Parse log entry to extract source
                        const logText = logEntry.text;
                        const sourceMatch = logText.match(/^\[([^\]]+)\]/);
                        const source = sourceMatch ? sourceMatch[1] : null;
                        const message = sourceMatch ? logText.substring(sourceMatch[0].length).trim() : logText;
                        
                        // Determine icon and color based on source
                        let icon = "📋"; // Default
                        let sourceColor = "text-gray-400";
                        
                        if (source) {
                          const sourceLower = source.toLowerCase();
                          if (sourceLower.includes("planner") || sourceLower.includes("router")) {
                            icon = "🧠"; // Brain for planner
                            sourceColor = "text-purple-400";
                          } else if (sourceLower.includes("executor")) {
                            icon = "⚡"; // Lightning for executor
                            sourceColor = "text-yellow-400";
                          } else if (sourceLower.includes("api")) {
                            icon = "🔌"; // Plug for API
                            sourceColor = "text-blue-400";
                          } else if (sourceLower.includes("callback")) {
                            icon = "🔄"; // Loop for callbacks
                            sourceColor = "text-green-400";
                          } else if (sourceLower.includes("admin")) {
                            icon = "👤"; // User for admin
                            sourceColor = "text-cyan-400";
                          } else if (sourceLower.includes("demo")) {
                            icon = "🧪"; // Test tube for demo
                            sourceColor = "text-pink-400";
                          } else if (sourceLower.includes("checkpointer")) {
                            icon = "💾"; // Disk for storage
                            sourceColor = "text-indigo-400";
                          } else {
                            icon = "🤖"; // Robot for other AI agents
                            sourceColor = "text-emerald-400";
                          }
                        }
                        
                        return (
                          <div key={logEntry.id} className="hover:bg-gray-800/50 px-2 -mx-2 rounded flex items-start gap-2">
                            <span className="text-gray-600 select-none text-xs flex-shrink-0 mt-0.5">
                              {logEntry.timestamp.toLocaleTimeString()}
                            </span>
                            {source && (
                              <>
                                <span className="flex-shrink-0" title={source}>
                                  {icon}
                                </span>
                                <span className={`${sourceColor} font-semibold flex-shrink-0`}>
                                  [{source}]
                                </span>
                              </>
                            )}
                            <span className="whitespace-pre-wrap break-all flex-1">
                              {message}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === "metadata" && (
              <div className="space-y-6">
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Checkpoint Metadata</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto text-sm font-mono">
                    {JSON.stringify(run?.metadata || {}, null, 2)}
                  </pre>
                </div>
                {run?.pending_writes && run.pending_writes.length > 0 && (
                  <div className="bg-white rounded-lg border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Pending Writes</h3>
                    <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto text-sm font-mono">
                      {JSON.stringify(run.pending_writes, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* HITL Modal */}
      {showHitlModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white border border-gray-200 rounded-lg shadow-2xl max-w-3xl w-full mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-red-50">
              <div>
                <h3 className="text-lg font-semibold text-red-800">Human Review Required</h3>
                <p className="text-sm text-red-600 mt-1">Triggered by: {awaitingSkill}</p>
              </div>
              <button
                onClick={() => setShowHitlModal(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm text-gray-700">
                Review and optionally edit the data store below, then approve to continue the workflow.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Data Store (JSON)
                </label>
                <textarea
                  value={hitlData}
                  onChange={(e) => setHitlData(e.target.value)}
                  className="w-full h-64 bg-gray-900 text-green-400 font-mono p-4 rounded border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                  spellCheck={false}
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex gap-4 bg-gray-50">
              <button
                onClick={() => handleApprove(false)}
                disabled={approving}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-bold py-3 rounded transition-colors"
              >
                {approving ? "Approving..." : "Approve & Continue"}
              </button>
              <button
                onClick={() => handleApprove(true)}
                disabled={approving}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-3 rounded transition-colors"
              >
                {approving ? "Approving..." : "Approve with Changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
