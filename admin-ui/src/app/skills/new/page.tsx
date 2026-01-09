"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createSkill, Skill } from "../../../lib/api";
import DashboardLayout from "../../../components/DashboardLayout";

export default function NewSkillPage() {
  const router = useRouter();
  const [formData, setFormData] = useState<Partial<Skill>>({
    name: "",
    description: "",
    requires: [],
    produces: [],
    executor: "llm",
    hitl_enabled: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // String versions for input fields
  const [requiresStr, setRequiresStr] = useState("");
  const [producesStr, setProducesStr] = useState("");

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);

    // Validate
    if (!formData.name?.trim()) {
      setError("Skill name is required");
      setLoading(false);
      return;
    }

    if (!formData.description?.trim()) {
      setError("Description is required");
      setLoading(false);
      return;
    }

    // Parse comma-separated lists
    const requires = requiresStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const produces = producesStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const skillData: Skill = {
      ...formData as Skill,
      requires,
      produces,
    };

    try {
      const result = await createSkill(skillData);
      alert(`Skill created successfully! Total skills: ${result.total_skills}`);
      router.push("/skills");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

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
          <h1 className="text-3xl font-bold text-gray-900">Create New Skill</h1>
          <p className="mt-2 text-sm text-gray-600">
            Build a new agent skill dynamically
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
                  Skill Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="MyCustomSkill"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-900 mb-2">
                  Description *
                </label>
                <textarea
                  value={formData.description}
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
            </div>
          </div>

          {/* Executor Type */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Executor Type
            </h3>

            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="llm"
                    checked={formData.executor === "llm"}
                    onChange={(e) =>
                      setFormData({ ...formData, executor: e.target.value as any })
                    }
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm font-medium">LLM (AI-powered)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="rest"
                    checked={formData.executor === "rest"}
                    onChange={(e) =>
                      setFormData({ ...formData, executor: e.target.value as any })
                    }
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm font-medium">REST (API call)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="action"
                    checked={formData.executor === "action"}
                    onChange={(e) =>
                      setFormData({ ...formData, executor: e.target.value as any })
                    }
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm font-medium">
                    Action (Deterministic)
                  </span>
                </label>
              </div>

              {/* LLM Fields */}
              {formData.executor === "llm" && (
                <div className="space-y-4 mt-4 p-4 bg-purple-50 rounded-lg">
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

              {/* Note for REST/Action */}
              {formData.executor === "rest" && (
                <div className="mt-4 p-4 bg-orange-50 rounded-lg">
                  <p className="text-sm text-orange-800">
                    REST executor configuration will be available in the full editor.
                    For now, create as LLM and edit the database directly.
                  </p>
                </div>
              )}

              {formData.executor === "action" && (
                <div className="mt-4 p-4 bg-pink-50 rounded-lg">
                  <p className="text-sm text-pink-800">
                    Action executor configuration will be available in the full editor.
                    For now, create as LLM and edit the database directly.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Options */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Options</h3>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.hitl_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, hitl_enabled: e.target.checked })
                }
                className="w-4 h-4 text-blue-600 rounded"
              />
              <span className="text-sm font-medium text-gray-900">
                Enable Human-in-the-Loop (HITL)
              </span>
            </label>
            <p className="mt-2 text-xs text-gray-600 ml-6">
              Pause workflow for human review after this skill executes
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-4">
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              {loading ? "Creating..." : "Create Skill"}
            </button>
            <Link
              href="/skills"
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
