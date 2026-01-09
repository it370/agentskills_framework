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
  
  // Action executor fields
  const [actionType, setActionType] = useState("python_function");
  const [actionSource, setActionSource] = useState(""); // For data_query: postgres, mysql, etc.
  const [credentialRef, setCredentialRef] = useState("");
  const [actionCodeOrQuery, setActionCodeOrQuery] = useState("");
  
  // REST executor fields
  const [restUrl, setRestUrl] = useState("");
  const [restMethod, setRestMethod] = useState("GET");
  const [restTimeout, setRestTimeout] = useState("30000");

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
    
    // Add REST config if REST executor
    if (formData.executor === "rest") {
      skillData.rest_config = {
        url: restUrl,
        method: restMethod,
        timeout: parseInt(restTimeout) || 30000,
        headers: {},
      };
    }
    
    // Add Action config if Action executor
    if (formData.executor === "action") {
      skillData.action_config = {
        type: actionType,
      };
      
      // For data_query, source is required
      if (actionType === "data_query") {
        if (!actionSource.trim()) {
          setError("Data source is required for data_query actions");
          setLoading(false);
          return;
        }
        skillData.action_config.source = actionSource;
        skillData.action_config.query = actionCodeOrQuery;
      }
      
      if (credentialRef.trim()) {
        skillData.action_config.credential_ref = credentialRef.trim();
      }
      
      if (actionType === "python_function" && actionCodeOrQuery.trim()) {
        skillData.action_code = actionCodeOrQuery;
      }
    }

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
                  <p className="text-sm text-orange-800 mb-2 font-medium">
                    REST Executor Configuration
                  </p>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-900 mb-1">
                        URL
                      </label>
                      <input
                        type="text"
                        value={restUrl}
                        onChange={(e) => setRestUrl(e.target.value)}
                        placeholder="https://api.example.com/endpoint"
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-900 mb-1">
                          Method
                        </label>
                        <select
                          value={restMethod}
                          onChange={(e) => setRestMethod(e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option>GET</option>
                          <option>POST</option>
                          <option>PUT</option>
                          <option>DELETE</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-900 mb-1">
                          Timeout (ms)
                        </label>
                        <input
                          type="number"
                          value={restTimeout}
                          onChange={(e) => setRestTimeout(e.target.value)}
                          placeholder="30000"
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {formData.executor === "action" && (
                <div className="mt-4 space-y-4">
                  <div className="p-4 bg-pink-50 rounded-lg">
                    <p className="text-sm text-pink-800 mb-3 font-medium">
                      Action Executor Configuration
                    </p>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-900 mb-1">
                          Action Type *
                        </label>
                        <select
                          value={actionType}
                          onChange={(e) => setActionType(e.target.value)}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="python_function">Python Function (Inline Code)</option>
                          <option value="data_query">Data Query (SQL)</option>
                          <option value="data_pipeline">Data Pipeline (Multi-step)</option>
                          <option value="rest_call">REST API Call</option>
                        </select>
                      </div>
                      
                      {actionType === "data_query" && (
                        <div>
                          <label className="block text-xs font-medium text-gray-900 mb-1">
                            Data Source * <span className="text-xs text-gray-500">(Database Type)</span>
                          </label>
                          <select
                            value={actionSource}
                            onChange={(e) => setActionSource(e.target.value)}
                            className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="">Select database type...</option>
                            <option value="postgres">PostgreSQL</option>
                            <option value="mysql">MySQL</option>
                            <option value="sqlite">SQLite</option>
                            <option value="mongodb">MongoDB</option>
                          </select>
                          <p className="text-xs text-gray-600 mt-1">
                            Type of database connection
                          </p>
                        </div>
                      )}
                      
                      <div>
                        <label className="block text-xs font-medium text-gray-900 mb-1">
                          Credential Reference {actionType === "data_query" ? "*" : "(optional)"}
                        </label>
                        <input
                          type="text"
                          value={credentialRef}
                          onChange={(e) => setCredentialRef(e.target.value)}
                          placeholder="postgres_aiven_cloud_db, my_api_key"
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <p className="text-xs text-gray-600 mt-1">
                          Name of credential from vault (e.g., postgres_aiven_cloud_db)
                        </p>
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">
                      {actionType === "data_query" 
                        ? "SQL Query" 
                        : actionType === "data_pipeline" 
                        ? "Action Pipeline" 
                        : "Python Code"}
                    </label>
                    <textarea
                      value={actionCodeOrQuery}
                      onChange={(e) => setActionCodeOrQuery(e.target.value)}
                      placeholder={
                        actionType === "data_query"
                          ? "SELECT * FROM users WHERE id = {user_id}"
                          : actionType === "data_pipeline"
                          ? `steps:
  - type: query
    name: fetch_sales
    source: postgres
    credential_ref: postgres_aiven_cloud_db
    query: "SELECT * FROM sales WHERE date >= {start_date}"
    outputs: [sales_data]
  
  - type: query
    name: fetch_expenses
    source: postgres
    credential_ref: postgres_aiven_cloud_db
    query: "SELECT * FROM expenses WHERE date >= {start_date}"
    outputs: [expense_data]
  
  - type: merge
    name: combine_data
    inputs: [sales_data, expense_data]
    output: raw_financial_data
  
  - type: skill
    name: llm_analysis
    skill: FinancialAnalyzer
    inputs: [raw_financial_data]
  
  - type: transform
    name: compute_metrics
    function: compute_financial_metrics
    inputs: [raw_financial_data]
    outputs: [computed_metrics]
  
  - type: transform
    name: format_report
    function: format_financial_report
    inputs: [computed_metrics]
    outputs: [final_report]`
                          : "def my_function(data_store, **kwargs):\n    # Your code here\n    return {'result': 'value'}"
                      }
                      className="w-full h-48 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm bg-gray-900 text-gray-100"
                    />
                    <p className="text-xs text-gray-600 mt-2">
                      {actionType === "python_function" && (
                        <>
                          Write a Python function that accepts <code className="bg-gray-100 px-1 rounded">data_store</code> and returns a dict.
                        </>
                      )}
                      {actionType === "data_query" && (
                        <>
                          Write SQL with <code className="bg-gray-100 px-1 rounded">{'"{param}"'}</code> placeholders from data_store.
                        </>
                      )}
                      {actionType === "data_pipeline" && (
                        <>
                          Define multi-step pipeline with <code className="bg-gray-100 px-1 rounded">query</code>, <code className="bg-gray-100 px-1 rounded">transform</code>, <code className="bg-gray-100 px-1 rounded">skill</code>, and <code className="bg-gray-100 px-1 rounded">merge</code> steps. Edit in database after creation for complex pipelines.
                        </>
                      )}
                    </p>
                  </div>
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
