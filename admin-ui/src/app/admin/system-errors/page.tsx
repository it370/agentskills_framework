"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import DashboardLayout from "@/components/DashboardLayout";
import ProtectedRoute from "@/components/ProtectedRoute";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";
// const API_BASE = "http://localhost:3000/api/mock";

interface SystemError {
  id: number;
  error_type: string;
  severity: "warning" | "error" | "critical";
  thread_id: string | null;
  error_message: string;
  stack_trace: string | null;
  error_context: any;
  created_at: string;
}

interface ErrorsResponse {
  status: string;
  count: number;
  errors: SystemError[];
  filters: {
    error_type: string | null;
    severity: string | null;
    limit: number;
  };
}

export default function SystemErrorsPage() {
  const { user, token } = useAuth();
  const router = useRouter();
  const [errors, setErrors] = useState<SystemError[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorFilter, setErrorFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [selectedError, setSelectedError] = useState<SystemError | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState<string>("");
  const [resolving, setResolving] = useState<number | null>(null);

  // Redirect if not admin
  useEffect(() => {
    if (!user?.is_admin) {
      router.push("/");
    }
  }, [user, router]);

  useEffect(() => {
    if (user?.is_admin && token) {
      fetchErrors();
    }
  }, [user, token, errorFilter, severityFilter]);

  async function fetchErrors() {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (errorFilter) params.append("error_type", errorFilter);
      if (severityFilter) params.append("severity", severityFilter);
      params.append("limit", "100");

      const res = await fetch(`${API_BASE}/admin/system-errors?${params}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error("Failed to fetch system errors");
      }

      const data: ErrorsResponse = await res.json();
      setErrors(data.errors);
    } catch (error) {
      console.error("Error fetching system errors:", error);
    } finally {
      setLoading(false);
    }
  }

  async function resolveError(errorId: number) {
    try {
      setResolving(errorId);
      const res = await fetch(`${API_BASE}/admin/system-errors/${errorId}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          resolution_notes: resolutionNotes || undefined,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to resolve error");
      }

      // Remove resolved error from list
      setErrors((prev) => prev.filter((e) => e.id !== errorId));
      setSelectedError(null);
      setResolutionNotes("");
    } catch (error) {
      console.error("Error resolving system error:", error);
      alert("Failed to resolve error");
    } finally {
      setResolving(null);
    }
  }

  if (!user?.is_admin) {
    return null;
  }

  const severityColors = {
    warning: "bg-yellow-100 text-yellow-800 border-yellow-300",
    error: "bg-orange-100 text-orange-800 border-orange-300",
    critical: "bg-red-100 text-red-800 border-red-300",
  };

  const severityBadgeColors = {
    warning: "bg-yellow-500",
    error: "bg-orange-500",
    critical: "bg-red-500",
  };

  return (
    <ProtectedRoute>
      <DashboardLayout>
        <div className="p-6">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900">System Errors</h1>
            <p className="text-gray-600 mt-1">
              Critical system errors requiring admin attention
            </p>
          </div>

          {/* Filters */}
          <div className="mb-6 bg-white rounded-lg shadow p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Severity
                </label>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Severities</option>
                  <option value="critical">Critical</option>
                  <option value="error">Error</option>
                  <option value="warning">Warning</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Error Type
                </label>
                <select
                  value={errorFilter}
                  onChange={(e) => setErrorFilter(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Types</option>
                  <option value="checkpoint_flush_error">Checkpoint Flush Error</option>
                </select>
              </div>
              <div className="flex items-end">
                <button
                  onClick={fetchErrors}
                  className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
                >
                  Refresh
                </button>
              </div>
            </div>
          </div>

          {/* Error Count */}
          <div className="mb-4">
            <p className="text-sm text-gray-600">
              {loading ? "Loading..." : `${errors.length} unresolved error${errors.length !== 1 ? "s" : ""}`}
            </p>
          </div>

          {/* Errors List */}
          <div className="grid grid-cols-1 gap-4">
            {loading ? (
              <div className="bg-white rounded-lg shadow p-8 text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                <p className="mt-4 text-gray-600">Loading system errors...</p>
              </div>
            ) : errors.length === 0 ? (
              <div className="bg-white rounded-lg shadow p-8 text-center">
                <div className="text-6xl mb-4">✅</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  No Unresolved Errors
                </h3>
                <p className="text-gray-600">
                  All system errors have been resolved. Great work!
                </p>
              </div>
            ) : (
              errors.map((error) => (
                <div
                  key={error.id}
                  className={`border-l-4 rounded-lg shadow p-5 bg-white ${selectedError?.id === error.id ? "ring-2 ring-blue-500" : ""
                    }`}
                  style={{
                    borderLeftColor:
                      error.severity === "critical"
                        ? "#ef4444"
                        : error.severity === "error"
                          ? "#f97316"
                          : "#eab308",
                  }}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <span
                        className={`inline-block px-2 py-1 text-xs font-semibold rounded ${severityColors[error.severity]}`}
                      >
                        {error.severity.toUpperCase()}
                      </span>
                      <span className="text-sm font-medium text-gray-700">
                        {error.error_type}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(error.created_at).toLocaleString()}
                    </span>
                  </div>

                  <p className="text-gray-900 mb-3 font-medium">{error.error_message}</p>

                  {error.thread_id && (
                    <p className="text-sm text-gray-600 mb-2">
                      <span className="font-medium">Thread:</span>{" "}
                      <a
                        href={`/admin/${error.thread_id}`}
                        className="text-blue-600 hover:underline"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {error.thread_id}
                      </a>
                    </p>
                  )}

                  {error.error_context && (
                    <div className="mb-3">
                      <p className="text-xs font-medium text-gray-700 mb-1">Context:</p>
                      <div className="bg-gray-50 rounded p-2 text-xs font-mono">
                        {Object.entries(error.error_context).map(([key, value]) => (
                          <div key={key}>
                            <span className="text-gray-600">{key}:</span>{" "}
                            <span className="text-gray-900">{JSON.stringify(value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        setSelectedError(selectedError?.id === error.id ? null : error)
                      }
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {selectedError?.id === error.id
                        ? "Hide Details"
                        : "View Stack Trace"}
                    </button>
                    <button
                      onClick={() => {
                        setSelectedError(error);
                        setResolutionNotes("");
                      }}
                      className="text-sm text-green-600 hover:text-green-800 font-medium"
                    >
                      Mark as Resolved
                    </button>
                  </div>

                  {/* Stack Trace Modal */}
                  {selectedError?.id === error.id && error.stack_trace && (
                    <div className="mt-4 bg-gray-900 rounded-lg p-4 overflow-x-auto">
                      <div className="flex justify-between items-center mb-2">
                        <p className="text-xs font-medium text-gray-400">
                          STACK TRACE
                        </p>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(error.stack_trace || "");
                            alert("Stack trace copied to clipboard");
                          }}
                          className="text-xs text-blue-400 hover:text-blue-300"
                        >
                          Copy
                        </button>
                      </div>
                      <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
                        {error.stack_trace}
                      </pre>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Resolution Modal */}
          {selectedError && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
              <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">
                  Resolve Error #{selectedError.id}
                </h3>
                <div className="mb-4">
                  <p className="text-sm text-gray-600 mb-2">
                    {selectedError.error_message}
                  </p>
                  <span
                    className={`inline-block px-2 py-1 text-xs font-semibold rounded ${severityColors[selectedError.severity]}`}
                  >
                    {selectedError.severity.toUpperCase()}
                  </span>
                </div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Resolution Notes (optional)
                  </label>
                  <textarea
                    value={resolutionNotes}
                    onChange={(e) => setResolutionNotes(e.target.value)}
                    placeholder="Describe how this error was fixed..."
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 h-32"
                  />
                </div>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => {
                      setSelectedError(null);
                      setResolutionNotes("");
                    }}
                    disabled={resolving !== null}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => resolveError(selectedError.id)}
                    disabled={resolving !== null}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50 flex items-center gap-2"
                  >
                    {resolving === selectedError.id ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        Resolving...
                      </>
                    ) : (
                      "Mark as Resolved"
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </DashboardLayout>
    </ProtectedRoute>
  );
}
