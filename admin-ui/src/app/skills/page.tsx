"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchSkills, deleteSkill, reloadSkills, Skill } from "../../lib/api";
import DashboardLayout from "../../components/DashboardLayout";
import { useAppSelector } from "@/store/hooks";

export default function SkillsPage() {
  const router = useRouter();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "filesystem" | "database">("all");
  const [executorFilter, setExecutorFilter] = useState<string>("all");
  const [actionTypeFilter, setActionTypeFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [reloading, setReloading] = useState(false);
  const [deletingSkill, setDeletingSkill] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const { activeWorkspaceId } = useAppSelector((state) => state.workspace);

  const loadSkills = async () => {
    try {
      setLoading(true);
      const data = await fetchSkills();
      setSkills(data.skills);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkills();
  }, [activeWorkspaceId]);

  const handleReload = async () => {
    setReloading(true);
    try {
      const result = await reloadSkills();
      await loadSkills();
      alert(`Successfully reloaded ${result.total_skills} skills!`);
    } catch (err: any) {
      alert(`Failed to reload: ${err.message}`);
    } finally {
      setReloading(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete skill "${name}"? This cannot be undone.`)) {
      return;
    }

    setDeletingSkill(name);
    try {
      await deleteSkill(name);
      await loadSkills();
    } catch (err: any) {
      alert(`Failed to delete: ${err.message}`);
    } finally {
      setDeletingSkill(null);
    }
  };

  const filteredSkills = skills.filter((skill) => {
    const matchesSource =
      filter === "all" ||
      (filter === "filesystem" && skill.source !== "database") ||
      (filter === "database" && skill.source === "database");

    const matchesExecutor =
      executorFilter === "all" || skill.executor === executorFilter;

    const matchesActionType =
      actionTypeFilter === "all" ||
      (skill.executor === "action" && 
       skill.action_config?.type === actionTypeFilter);

    const matchesSearch =
      !searchTerm ||
      skill.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      skill.description.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesSource && matchesExecutor && matchesActionType && matchesSearch;
  });

  // Pagination calculations
  const totalPages = Math.ceil(filteredSkills.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedSkills = filteredSkills.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [filter, executorFilter, actionTypeFilter, searchTerm]);

  const stats = {
    total: skills.length,
    filesystem: skills.filter((s) => s.source !== "database").length,
    database: skills.filter((s) => s.source === "database").length,
    llm: skills.filter((s) => s.executor === "llm").length,
    rest: skills.filter((s) => s.executor === "rest").length,
    action: skills.filter((s) => s.executor === "action").length,
    // Action type stats
    data_query: skills.filter((s) => s.executor === "action" && s.action_config?.type === "data_query").length,
    data_pipeline: skills.filter((s) => s.executor === "action" && s.action_config?.type === "data_pipeline").length,
    python_function: skills.filter((s) => s.executor === "action" && s.action_config?.type === "python_function").length,
  };

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Agent Skill Builder
              </h1>
              <p className="mt-2 text-sm text-gray-600">
                Create, manage, and reload agent skills dynamically
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleReload}
                disabled={reloading}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                title="Reload all skills (hot-reload)"
              >
                <svg
                  className={`w-4 h-4 ${reloading ? "animate-spin" : ""}`}
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
                {reloading ? "Reloading..." : "Reload Skills"}
              </button>
              <Link
                href="/skills/new"
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
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
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Create Skill
              </Link>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-6 flex items-center gap-6 bg-white rounded-lg border border-gray-200 px-6 py-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">Total</span>
              <span className="text-lg font-bold text-gray-900">
                {stats.total}
              </span>
            </div>
            <div className="w-px h-8 bg-gray-200"></div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">
                Filesystem
              </span>
              <span className="text-lg font-bold text-blue-600">
                {stats.filesystem}
              </span>
            </div>
            <div className="w-px h-8 bg-gray-200"></div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">
                Database
              </span>
              <span className="text-lg font-bold text-green-600">
                {stats.database}
              </span>
            </div>
            <div className="w-px h-8 bg-gray-200"></div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">LLM</span>
              <span className="text-lg font-bold text-purple-600">
                {stats.llm}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">REST</span>
              <span className="text-lg font-bold text-orange-600">
                {stats.rest}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">Action</span>
              <span className="text-lg font-bold text-pink-600">
                {stats.action}
              </span>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1 min-w-[250px]">
              <input
                type="text"
                placeholder="Search skills..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <select
              value={filter}
              onChange={(e) =>
                setFilter(e.target.value as "all" | "filesystem" | "database")
              }
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Sources</option>
              <option value="filesystem">Filesystem Only</option>
              <option value="database">Database Only</option>
            </select>
            <select
              value={executorFilter}
              onChange={(e) => setExecutorFilter(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Executors</option>
              <option value="llm">LLM</option>
              <option value="rest">REST</option>
              <option value="action">Action</option>
            </select>
            {executorFilter === "action" && (
              <select
                value={actionTypeFilter}
                onChange={(e) => setActionTypeFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 animate-fadeIn"
              >
                <option value="all">All Action Types</option>
                <option value="data_query">Data Query</option>
                <option value="data_pipeline">Data Pipeline</option>
                <option value="python_function">Python Function</option>
              </select>
            )}
            <select
              value={itemsPerPage}
              onChange={(e) => {
                setItemsPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="10">10 per page</option>
              <option value="25">25 per page</option>
              <option value="50">50 per page</option>
              <option value="100">100 per page</option>
            </select>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Skills List */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <p className="text-gray-600">
              {searchTerm || filter !== "all" || executorFilter !== "all" || actionTypeFilter !== "all"
                ? "No skills match your filters"
                : "No skills found. Create your first skill!"}
            </p>
          </div>
        ) : paginatedSkills.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <p className="text-gray-600">
              No skills on this page. Please adjust pagination or filters.
            </p>
          </div>
        ) : (
          <>
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto divide-y divide-gray-200 min-w-[1000px]">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[100px] truncate">
                        Skill Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[320px]">
                        Description
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Executor
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Action Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Source
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Visibility
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {paginatedSkills.map((skill) => (
                      <tr key={skill.name} className="hover:bg-gray-50">
                        <td className="px-6 py-4 w-[150px]">
                          <div className="text-sm font-medium text-gray-900 w-[220px] truncate">
                            {skill.name}
                          </div>
                        </td>
                        <td className="px-6 py-4 w-[320px]">
                          <div className="text-xs text-gray-600 max-w-[320px] truncate">
                            {skill.description}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              skill.executor === "llm"
                                ? "bg-purple-100 text-purple-800"
                                : skill.executor === "rest"
                                ? "bg-orange-100 text-orange-800"
                                : "bg-pink-100 text-pink-800"
                            }`}
                          >
                            {skill.executor.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {skill.executor === "action" && skill.action_config?.type ? (
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                skill.action_config.type === "data_query"
                                  ? "bg-cyan-100 text-cyan-800"
                                  : skill.action_config.type === "data_pipeline"
                                  ? "bg-indigo-100 text-indigo-800"
                                  : "bg-teal-100 text-teal-800"
                              }`}
                            >
                              {skill.action_config.type === "data_query"
                                ? "Data Query"
                                : skill.action_config.type === "data_pipeline"
                                ? "Pipeline"
                                : "Python"}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              skill.source === "database"
                                ? "bg-green-100 text-green-800"
                                : "bg-blue-100 text-blue-800"
                            }`}
                          >
                            {skill.source === "database" ? "Database" : "Filesystem"}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              skill.is_public
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {skill.is_public ? "Public" : "Workspace-only"}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <div className="flex items-center gap-2">
                            <Link
                              href={`/skills/${encodeURIComponent(skill.name)}`}
                              className="text-blue-600 hover:text-blue-800"
                            >
                              View
                            </Link>
                            {skill.source === "database" && (
                              <>
                                <span className="text-gray-300">|</span>
                                <Link
                                  href={`/skills/${encodeURIComponent(
                                    skill.name
                                  )}/edit`}
                                  className="text-blue-600 hover:text-blue-800"
                                >
                                  Edit
                                </Link>
                                <span className="text-gray-300">|</span>
                                <button
                                  onClick={() => handleDelete(skill.name)}
                                  disabled={deletingSkill === skill.name}
                                  className="text-red-600 hover:text-red-800 disabled:opacity-50"
                                >
                                  {deletingSkill === skill.name
                                    ? "Deleting..."
                                    : "Delete"}
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between bg-white rounded-lg border border-gray-200 px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-700">
                    Showing <span className="font-medium">{startIndex + 1}</span> to{" "}
                    <span className="font-medium">
                      {Math.min(endIndex, filteredSkills.length)}
                    </span>{" "}
                    of <span className="font-medium">{filteredSkills.length}</span> results
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  
                  <div className="flex items-center gap-1">
                    {Array.from({ length: totalPages }, (_, i) => i + 1)
                      .filter((page) => {
                        // Show first page, last page, current page, and 2 pages around current
                        return (
                          page === 1 ||
                          page === totalPages ||
                          Math.abs(page - currentPage) <= 1
                        );
                      })
                      .map((page, idx, arr) => (
                        <div key={page} className="flex items-center">
                          {idx > 0 && arr[idx - 1] !== page - 1 && (
                            <span className="px-2 text-gray-400">...</span>
                          )}
                          <button
                            onClick={() => setCurrentPage(page)}
                            className={`px-3 py-2 border rounded-lg text-sm font-medium ${
                              currentPage === page
                                ? "bg-blue-600 text-white border-blue-600"
                                : "border-gray-300 text-gray-700 hover:bg-gray-50"
                            }`}
                          >
                            {page}
                          </button>
                        </div>
                      ))}
                  </div>

                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
