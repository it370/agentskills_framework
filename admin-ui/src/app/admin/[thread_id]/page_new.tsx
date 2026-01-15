"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import DashboardLayout from "../../../components/DashboardLayout";
import { useRun } from "../../../contexts/RunContext";
import { useAppSelector } from "../../../store/hooks";

export default function RunDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const threadId = params?.thread_id as string;
  
  const { initializeRun, loadHistoricalData } = useRun();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(searchParams.get("tab") || "config");
  
  // Get data from Redux store
  const runData = useAppSelector((state) => state.run.runs[threadId]);
  const logs = useAppSelector((state) => state.logs.logsByThread[threadId] || []);
  const historicalLogsLoaded = useAppSelector((state) => state.logs.historicalLogsLoaded[threadId]);

  // Load data on mount
  useEffect(() => {
    if (!threadId) return;
    
    const init = async () => {
      try {
        // Check if we already have data in store
        if (runData?.metadata) {
          console.log("[RunDetail] Data already in store, skipping load");
          setLoading(false);
          return;
        }
        
        // No data in store - this is a fresh page load or refresh
        console.log("[RunDetail] Loading historical data (page refresh scenario)");
        await initializeRun(threadId);
        await loadHistoricalData(threadId);
        setLoading(false);
      } catch (err: any) {
        console.error("[RunDetail] Failed to load data:", err);
        setError(err.message);
        setLoading(false);
      }
    };
    
    init();
  }, [threadId]); // Only run on mount or threadId change

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading run details...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="p-8">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h3 className="text-red-800 font-semibold mb-2">Error Loading Run</h3>
            <p className="text-red-700">{error}</p>
            <Link href="/" className="text-red-600 hover:text-red-800 underline mt-2 inline-block">
              Back to Runs
            </Link>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const metadata = runData?.metadata;
  const checkpoint = runData?.checkpoint;
  const runName = metadata?.run_name || threadId;
  const status = metadata?.status || 'unknown';
  
  const history = (checkpoint?.checkpoint?.channel_values?.history ||
    checkpoint?.checkpoint?.history ||
    []) as string[];

  const activeSkill = checkpoint?.checkpoint?.channel_values?.active_skill ||
    checkpoint?.checkpoint?.active_skill;

  const dataStore = checkpoint?.checkpoint?.channel_values?.data_store || 
    checkpoint?.checkpoint?.data_store || {};

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to Runs
            </Link>
            <h1 className="text-3xl font-bold text-gray-900">{runName}</h1>
            <p className="mt-2 text-sm text-gray-600">Thread ID: {threadId}</p>
          </div>
          <div>
            <StatusBadge status={status} />
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="flex gap-8">
            {['config', 'checkpoint', 'logs'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'config' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Workflow Configuration</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">SOP</label>
                  <pre className="mt-2 p-4 bg-gray-50 rounded-lg text-sm overflow-x-auto">
                    {metadata?.sop || 'No SOP available'}
                  </pre>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Initial Data</label>
                  <pre className="mt-2 p-4 bg-gray-50 rounded-lg text-sm overflow-x-auto">
                    {JSON.stringify(metadata?.initial_data || {}, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'checkpoint' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">History</h2>
              <ul className="space-y-2">
                {history.length > 0 ? (
                  history.map((h, i) => (
                    <li key={i} className="text-sm text-gray-700 pl-4 border-l-2 border-gray-300">
                      {h}
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-gray-500 italic">No history yet</li>
                )}
              </ul>
            </div>
            
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Data Store</h2>
              <pre className="p-4 bg-gray-50 rounded-lg text-sm overflow-x-auto">
                {JSON.stringify(dataStore, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Live Logs</h2>
              <span className="text-sm text-gray-600">{logs.length} logs</span>
            </div>
            <div className="bg-gray-900 rounded-lg p-4 h-[600px] overflow-y-auto font-mono text-sm">
              {logs.length > 0 ? (
                logs.map((log) => (
                  <div key={log.id} className="text-gray-300 mb-1">
                    <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                    {log.message}
                  </div>
                ))
              ) : (
                <div className="text-gray-500 italic">No logs yet...</div>
              )}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function StatusBadge({ status }: { status: string }) {
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
      label: "Paused",
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
