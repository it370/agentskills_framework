"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchSkill, Skill } from "../../../lib/api";
import DashboardLayout from "../../../components/DashboardLayout";

export default function ViewSkillPage() {
  const params = useParams();
  const skillName = decodeURIComponent(params.skill_name as string);
  
  const [skill, setSkill] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchSkill(skillName);
        setSkill(data);
        setError(null);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [skillName]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !skill) {
    return (
      <DashboardLayout>
        <div className="p-8">
          <div className="rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-800">
              {error || "Skill not found"}
            </p>
          </div>
          <Link
            href="/skills"
            className="mt-4 inline-block text-blue-600 hover:text-blue-800"
          >
            ← Back to Skills
          </Link>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/skills"
            className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
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
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Skills
          </Link>

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{skill.name}</h1>
              <p className="mt-2 text-sm text-gray-600">{skill.description}</p>
            </div>
            <div className="flex items-center gap-3">
              {skill.source === "database" && (
                <Link
                  href={`/skills/${encodeURIComponent(skill.name)}/edit`}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
                >
                  Edit Skill
                </Link>
              )}
            </div>
          </div>

          {/* Badges */}
          <div className="mt-4 flex items-center gap-3">
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                skill.executor === "llm"
                  ? "bg-purple-100 text-purple-800"
                  : skill.executor === "rest"
                  ? "bg-orange-100 text-orange-800"
                  : "bg-pink-100 text-pink-800"
              }`}
            >
              {skill.executor.toUpperCase()}
            </span>
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                skill.source === "database"
                  ? "bg-green-100 text-green-800"
                  : "bg-blue-100 text-blue-800"
              }`}
            >
              {skill.source === "database" ? "Database" : "Filesystem"}
            </span>
            {skill.hitl_enabled && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800">
                HITL Enabled
              </span>
            )}
            {skill.enabled === false && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                Disabled
              </span>
            )}
          </div>
        </div>

        {/* Details */}
        <div className="max-w-5xl space-y-6">
          {/* I/O */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Input / Output
            </h3>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Required Inputs
                </label>
                {skill.requires.length > 0 ? (
                  <ul className="space-y-1">
                    {skill.requires.map((req) => (
                      <li
                        key={req}
                        className="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded"
                      >
                        <code>{req}</code>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500 italic">None</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Produced Outputs
                </label>
                {skill.produces.length > 0 ? (
                  <ul className="space-y-1">
                    {skill.produces.map((prod) => (
                      <li
                        key={prod}
                        className="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded"
                      >
                        <code>{prod}</code>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500 italic">None</p>
                )}
              </div>
            </div>
            {skill.optional_produces && skill.optional_produces.length > 0 && (
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Optional Outputs
                </label>
                <ul className="space-y-1">
                  {skill.optional_produces.map((prod) => (
                    <li
                      key={prod}
                      className="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded inline-block mr-2"
                    >
                      <code>{prod}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* LLM Configuration */}
          {skill.executor === "llm" && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                LLM Configuration
              </h3>
              {skill.prompt && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Prompt
                  </label>
                  <pre className="bg-gray-50 p-4 rounded text-sm text-gray-900 overflow-x-auto whitespace-pre-wrap">
                    {skill.prompt}
                  </pre>
                </div>
              )}
              {skill.system_prompt && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    System Prompt
                  </label>
                  <pre className="bg-gray-50 p-4 rounded text-sm text-gray-900 overflow-x-auto whitespace-pre-wrap">
                    {skill.system_prompt}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* REST Configuration */}
          {skill.executor === "rest" && skill.rest_config && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                REST Configuration
              </h3>
              <pre className="bg-gray-50 p-4 rounded text-sm text-gray-900 overflow-x-auto">
                {JSON.stringify(skill.rest_config, null, 2)}
              </pre>
            </div>
          )}

          {/* Action Configuration */}
          {skill.executor === "action" && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Action Configuration
              </h3>
              {skill.action_config && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Configuration
                  </label>
                  <pre className="bg-gray-50 p-4 rounded text-sm text-gray-900 overflow-x-auto">
                    {JSON.stringify(skill.action_config, null, 2)}
                  </pre>
                </div>
              )}
              {skill.action_code && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Python Code
                  </label>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded text-sm overflow-x-auto">
                    {skill.action_code}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Metadata */}
          {skill.source === "database" && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Metadata
              </h3>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                {skill.created_at && (
                  <>
                    <dt className="font-medium text-gray-700">Created At</dt>
                    <dd className="text-gray-900">
                      {new Date(skill.created_at).toLocaleString()}
                    </dd>
                  </>
                )}
                {skill.updated_at && (
                  <>
                    <dt className="font-medium text-gray-700">Updated At</dt>
                    <dd className="text-gray-900">
                      {new Date(skill.updated_at).toLocaleString()}
                    </dd>
                  </>
                )}
              </dl>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
