"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import DashboardLayout from "../../components/DashboardLayout";
import { useAuth } from "../../contexts/AuthContext";
import {
  fetchRunsManager,
  deleteRunsBulk,
  fetchRunManagerUsernames,
  fetchRunManagerWorkspaces,
  RunListItem,
} from "../../lib/api";

export default function RunManagerPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [usernameFilter, setUsernameFilter] = useState("");
  const [workspaceFilter, setWorkspaceFilter] = useState("");
  const [searchText, setSearchText] = useState("");
  
  // Filter options
  const [usernames, setUsernames] = useState<string[]>([]);
  const [allWorkspaces, setAllWorkspaces] = useState<Array<{ id: string; name: string; username?: string }>>([]);
  
  // Filtered workspaces based on selected username
  const filteredWorkspaces = usernameFilter
    ? allWorkspaces.filter((w) => w.username === usernameFilter)
    : allWorkspaces;
  
  // Selection
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);
  
  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Check if user is admin
  useEffect(() => {
    if (!authLoading && (!user || !user.is_admin)) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  // Load filter options
  useEffect(() => {
    const loadFilters = async () => {
      try {
        const [u, w] = await Promise.all([
          fetchRunManagerUsernames(),
          fetchRunManagerWorkspaces(),
        ]);
        setUsernames(u);
        setAllWorkspaces(w);
      } catch (err) {
        console.error("Failed to load filter options:", err);
      }
    };
    if (user?.is_admin) {
      loadFilters();
    }
  }, [user]);

  // Load runs
  useEffect(() => {
    if (!user?.is_admin) return;
    
    const loadRuns = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchRunsManager({
          page,
          page_size: pageSize,
          username: usernameFilter || undefined,
          workspace: workspaceFilter || undefined,
          search: searchText || undefined,
        });
        setRuns(response.runs);
        setTotal(response.total);
      } catch (err: any) {
        setError(err.message || "Failed to load runs");
      } finally {
        setLoading(false);
      }
    };

    loadRuns();
  }, [user, page, pageSize, usernameFilter, workspaceFilter, searchText]);

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedRuns(new Set());
    } else {
      setSelectedRuns(new Set(runs.map((r) => r.id)));
    }
    setSelectAll(!selectAll);
  };

  const handleSelectRun = (id: string) => {
    const newSelected = new Set(selectedRuns);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedRuns(newSelected);
    setSelectAll(newSelected.size === runs.length);
  };

  const handleDeleteClick = () => {
    if (selectedRuns.size === 0) return;
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    setDeleting(true);
    setShowDeleteConfirm(false);
    try {
      const result = await deleteRunsBulk(Array.from(selectedRuns));
      
      if (result.failed.length > 0) {
        alert(`Deleted ${result.deleted_count} runs. Failed to delete ${result.failed.length} runs.`);
      } else {
        alert(`Successfully deleted ${result.deleted_count} runs.`);
      }
      
      // Clear selection and reload
      setSelectedRuns(new Set());
      setSelectAll(false);
      
      // Reload the page
      const response = await fetchRunsManager({
        page,
        page_size: pageSize,
        username: usernameFilter || undefined,
        workspace: workspaceFilter || undefined,
        search: searchText || undefined,
      });
      setRuns(response.runs);
      setTotal(response.total);
    } catch (err: any) {
      alert(`Failed to delete runs: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const handleRowClick = (threadId: string) => {
    router.push(`/admin/${threadId}`);
  };

  const totalPages = Math.ceil(total / pageSize);

  if (authLoading || !user?.is_admin) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Run Manager</h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage all workflow runs with advanced filtering and bulk operations
          </p>
        </div>

        {/* Filters */}
        <div className="mb-4 bg-white rounded-lg border border-gray-200 p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Search
              </label>
              <input
                type="text"
                value={searchText}
                onChange={(e) => {
                  setSearchText(e.target.value);
                  setPage(1); // Reset to first page on search
                }}
                placeholder="Search ID or name..."
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Username Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Username
              </label>
              <select
                value={usernameFilter}
                onChange={(e) => {
                  setUsernameFilter(e.target.value);
                  // Reset workspace filter when changing username
                  setWorkspaceFilter("");
                  setPage(1);
                }}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Users</option>
                {usernames.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>

            {/* Workspace Filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Workspace {usernameFilter && `(${filteredWorkspaces.length})`}
              </label>
              <select
                value={workspaceFilter}
                onChange={(e) => {
                  setWorkspaceFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Workspaces</option>
                {filteredWorkspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Actions */}
            <div className="flex items-end">
              <button
                onClick={handleDeleteClick}
                disabled={selectedRuns.size === 0 || deleting}
                className="w-full px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                Delete Selected ({selectedRuns.size})
              </button>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Table */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectAll}
                      onChange={handleSelectAll}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Time
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Username
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Workspace
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                      Loading...
                    </td>
                  </tr>
                ) : runs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                      No runs found
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => (
                    <tr
                      key={run.id}
                      className="hover:bg-gray-50"
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedRuns.has(run.id)}
                          onChange={() => handleSelectRun(run.id)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleRowClick(run.id)}
                          className="text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline text-left"
                        >
                          {run.id.length > 20 ? `${run.id.substring(0, 20)}...` : run.id}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {run.name || "-"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={run.result} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600">
                        {run.time ? new Date(run.time).toLocaleString() : "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {run.username || "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {run.workspace_name || run.workspace || "-"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && runs.length > 0 && (
            <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
              <div className="text-sm text-gray-700">
                Showing {(page - 1) * pageSize + 1} to{" "}
                {Math.min(page * pageSize, total)} of {total} runs
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <div className="px-3 py-1 text-sm text-gray-700">
                  Page {page} of {totalPages}
                </div>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Delete Confirmation Modal */}
        {showDeleteConfirm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Confirm Deletion
              </h3>
              <p className="text-sm text-gray-600 mb-6">
                Are you sure you want to delete {selectedRuns.size} run(s)? This
                will permanently remove all traces including checkpoints, logs,
                and metadata. This action cannot be undone.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteConfirm}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function StatusBadge({ status }: { status?: string }) {
  if (!status) {
    return <span className="text-xs text-gray-500">-</span>;
  }

  const statusColors: Record<string, string> = {
    running: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    error: "bg-red-100 text-red-800",
    paused: "bg-yellow-100 text-yellow-800",
  };

  const color = statusColors[status.toLowerCase()] || "bg-gray-100 text-gray-800";

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {status}
    </span>
  );
}
