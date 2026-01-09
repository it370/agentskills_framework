"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { fetchSkill, updateSkill, Skill } from "../../../../lib/api";
import DashboardLayout from "../../../../components/DashboardLayout";

export default function EditSkillPage() {
  const params = useParams();
  const router = useRouter();
  const skillName = decodeURIComponent(params.skill_name as string);

  const [originalSkill, setOriginalSkill] = useState<Skill | null>(null);
  const [formData, setFormData] = useState<Partial<Skill>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // String versions for input fields
  const [requiresStr, setRequiresStr] = useState("");
  const [producesStr, setProducesStr] = useState("");
  const [optionalProducesStr, setOptionalProducesStr] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchSkill(skillName);
        
        if (data.source !== "database") {
          setError("Only database skills can be edited via UI");
          setLoading(false);
          return;
        }

        setOriginalSkill(data);
        setFormData(data);
        setRequiresStr((data.requires || []).join(", "));
        setProducesStr((data.produces || []).join(", "));
        setOptionalProducesStr((data.optional_produces || []).join(", "));
        setError(null);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [skillName]);

  const handleSubmit = async () => {
    setError(null);
    setSaving(true);

    try {
      // Parse comma-separated lists
      const requires = requiresStr
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const produces = producesStr
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const optional_produces = optionalProducesStr
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const updates: Partial<Skill> = {
        description: formData.description,
        requires,
        produces,
        optional_produces,
        executor: formData.executor,
        hitl_enabled: formData.hitl_enabled,
        prompt: formData.prompt,
        system_prompt: formData.system_prompt,
        rest_config: formData.rest_config,
        action_config: formData.action_config,
        action_code: formData.action_code,
        enabled: formData.enabled,
      };

      await updateSkill(skillName, updates);
      alert("Skill updated successfully!");
      router.push(`/skills/${encodeURIComponent(skillName)}`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error && !originalSkill) {
    return (
      <DashboardLayout>
        <div className="p-8">
          <div className="rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-800">{error}</p>
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
            href={`/skills/${encodeURIComponent(skillName)}`}
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
            Back to {skillName}
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">
            Edit Skill: {skillName}
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Modify skill configuration and settings
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Form */}
        <div className="max-w-4xl space-y-6">
          {/* Basic Info */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Basic Information
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  Skill Name
                </label>
                <input
                  type="text"
                  value={skillName}
                  disabled
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500 cursor-not-allowed"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Skill name cannot be changed
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  Description *
                </label>
                <textarea
                  value={formData.description || ""}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="w-full h-24 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="What does this skill do?"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    Required Inputs (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={requiresStr}
                    onChange={(e) => setRequiresStr(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="user_id, order_number"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    Produced Outputs (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={producesStr}
                    onChange={(e) => setProducesStr(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="user_data, result"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  Optional Outputs (comma-separated)
                </label>
                <input
                  type="text"
                  value={optionalProducesStr}
                  onChange={(e) => setOptionalProducesStr(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="metadata, debug_info"
                />
              </div>
            </div>
          </div>

          {/* Executor Config */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Executor Type: {formData.executor?.toUpperCase()}
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              Executor type cannot be changed after creation
            </p>

            {/* LLM Fields */}
            {formData.executor === "llm" && (
              <div className="space-y-4 p-4 bg-purple-50 rounded-lg">
                <div>
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    Prompt
                  </label>
                  <textarea
                    value={formData.prompt || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, prompt: e.target.value })
                    }
                    className="w-full h-32 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                    placeholder="Task instructions for the AI..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    System Prompt (Optional)
                  </label>
                  <textarea
                    value={formData.system_prompt || ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        system_prompt: e.target.value,
                      })
                    }
                    className="w-full h-24 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                    placeholder="Business rules, policies..."
                  />
                </div>
              </div>
            )}

            {/* REST/Action - JSON editor */}
            {formData.executor === "rest" && (
              <div className="p-4 bg-orange-50 rounded-lg">
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  REST Configuration (JSON)
                </label>
                <textarea
                  value={
                    formData.rest_config
                      ? JSON.stringify(formData.rest_config, null, 2)
                      : ""
                  }
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      setFormData({ ...formData, rest_config: parsed });
                    } catch {
                      // Invalid JSON, ignore
                    }
                  }}
                  className="w-full h-48 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  placeholder='{"url": "...", "method": "GET"}'
                />
              </div>
            )}

            {formData.executor === "action" && (
              <div className="space-y-4">
                <div className="p-4 bg-pink-50 rounded-lg">
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    Action Configuration (JSON)
                  </label>
                  <textarea
                    value={
                      formData.action_config
                        ? JSON.stringify(formData.action_config, null, 2)
                        : ""
                    }
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        setFormData({ ...formData, action_config: parsed });
                      } catch {
                        // Invalid JSON, ignore
                      }
                    }}
                    className="w-full h-32 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                    placeholder='{"type": "python_function"}'
                  />
                </div>

                <div className="p-4 bg-gray-50 rounded-lg">
                  <label className="block text-sm font-medium text-gray-900 mb-2">
                    Python Code (for python_function type)
                  </label>
                  <textarea
                    value={formData.action_code || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, action_code: e.target.value })
                    }
                    className="w-full h-64 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm bg-gray-900 text-gray-100"
                    placeholder="def my_function(data_store, **kwargs):&#10;    # Your code here&#10;    return {'result': 'value'}"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Options */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Options
            </h3>

            <div className="space-y-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.hitl_enabled || false}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      hitl_enabled: e.target.checked,
                    })
                  }
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-sm font-medium text-gray-900">
                  Enable Human-in-the-Loop (HITL)
                </span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.enabled !== false}
                  onChange={(e) =>
                    setFormData({ ...formData, enabled: e.target.checked })
                  }
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-sm font-medium text-gray-900">
                  Skill Enabled
                </span>
              </label>
              <p className="text-xs text-gray-600 ml-6">
                Disabled skills are not available in workflows
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-4">
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
            <Link
              href={`/skills/${encodeURIComponent(skillName)}`}
              className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition-colors flex items-center justify-center"
            >
              Cancel
            </Link>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
