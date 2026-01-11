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
  
  // Action executor fields
  const [actionType, setActionType] = useState("python_function");
  const [actionSource, setActionSource] = useState("");
  const [credentialRef, setCredentialRef] = useState("");
  const [actionCodeOrQuery, setActionCodeOrQuery] = useState("");
  const [pipelineFunctions, setPipelineFunctions] = useState(""); // For data_pipeline transform functions

  // REST executor fields
  const [restUrl, setRestUrl] = useState("");
  const [restMethod, setRestMethod] = useState("GET");
  const [restTimeout, setRestTimeout] = useState("30000");

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
        
        // Parse action config if present
        if (data.action_config) {
          setActionType(data.action_config.type || "python_function");
          setActionSource(data.action_config.source || "");
          setCredentialRef(data.action_config.credential_ref || "");
          if (data.action_config.query) {
            setActionCodeOrQuery(data.action_config.query);
          }
        }
        if (data.action_code) {
          setActionCodeOrQuery(data.action_code);
        }
        
        // Load pipeline functions if present
        if ((data as any).action_functions) {
          setPipelineFunctions((data as any).action_functions);
        }
        
        // Parse REST config if present
        if (data.rest_config) {
          setRestUrl(data.rest_config.url || "");
          setRestMethod(data.rest_config.method || "GET");
          setRestTimeout(String(data.rest_config.timeout || 30000));
        }
        
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
      };
      
      // Add REST config if REST executor
      if (formData.executor === "rest") {
        updates.rest_config = {
          url: restUrl,
          method: restMethod,
          timeout: parseInt(restTimeout) || 30000,
          headers: {},
        };
      }
      
      // Add Action config if Action executor
      if (formData.executor === "action") {
        updates.action_config = {
          type: actionType,
        };

        if (actionType === "data_query") {
          if (!actionSource.trim()) {
            setError("Data source is required for data_query actions");
            setLoading(false);
            return;
          }
          updates.action_config.source = actionSource;
          updates.action_config.query = actionCodeOrQuery;
        }

        // For data_pipeline, save the pipeline steps
        if (actionType === "data_pipeline") {
          if (!actionCodeOrQuery.trim()) {
            setError("Pipeline steps are required for data_pipeline actions");
            setLoading(false);
            return;
          }
          // Store the pipeline YAML/text in action_code for database storage
          updates.action_code = actionCodeOrQuery;
          
          // Store pipeline functions separately (will be saved to action_functions field)
          if (pipelineFunctions.trim()) {
            (updates as any).action_functions = pipelineFunctions;
          }
        }

        if (credentialRef.trim()) {
          updates.action_config.credential_ref = credentialRef.trim();
        }

        if (actionType === "python_function" && actionCodeOrQuery.trim()) {
          updates.action_code = actionCodeOrQuery;
        }
      }
      
      updates.enabled = formData.enabled;

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
            </div>

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

            {/* REST Config */}
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

            {/* Action Config */}
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
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-900">
                      {actionType === "data_query" 
                        ? "SQL Query" 
                        : actionType === "data_pipeline" 
                        ? "Action Pipeline" 
                        : "Python Code"}
                    </label>
                    
                    {/* Pipeline Step Type Buttons */}
                    {actionType === "data_pipeline" && (
                      <div className="flex gap-2 flex-wrap">
                        <button
                          type="button"
                          onClick={() => {
                            const template = `\n  - type: query
    name: my_query
    source: postgres
    credential_ref: postgres_aiven_cloud_db
    query: "SELECT * FROM table WHERE id = {param}"
    output: query_result\n`;
                            setActionCodeOrQuery(actionCodeOrQuery + template);
                          }}
                          className="px-3 py-1.5 text-xs font-medium bg-blue-100 hover:bg-blue-200 text-blue-700 border border-blue-300 rounded-md transition-colors shadow-sm"
                          title="Insert Query step"
                        >
                          + Query
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => {
                            const template = `\n  - type: transform
    name: my_transform
    function: my_function_name
    inputs: [input_data]
    output: transformed_result\n`;
                            setActionCodeOrQuery(actionCodeOrQuery + template);
                          }}
                          className="px-3 py-1.5 text-xs font-medium bg-green-100 hover:bg-green-200 text-green-700 border border-green-300 rounded-md transition-colors shadow-sm"
                          title="Insert Transform step"
                        >
                          + Transform
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => {
                            const template = `\n  - type: skill
    name: my_skill_invocation
    skill: MySkillName
    inputs: [input1, input2]\n`;
                            setActionCodeOrQuery(actionCodeOrQuery + template);
                          }}
                          className="px-3 py-1.5 text-xs font-medium bg-purple-100 hover:bg-purple-200 text-purple-700 border border-purple-300 rounded-md transition-colors shadow-sm"
                          title="Insert Skill step"
                        >
                          + Skill
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => {
                            const template = `\n  - type: merge
    name: combine_data
    inputs: [data1, data2, data3]
    output: merged_data\n`;
                            setActionCodeOrQuery(actionCodeOrQuery + template);
                          }}
                          className="px-3 py-1.5 text-xs font-medium bg-orange-100 hover:bg-orange-200 text-orange-700 border border-orange-300 rounded-md transition-colors shadow-sm"
                          title="Insert Merge step"
                        >
                          + Merge
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => {
                            const template = `\n  - type: parallel
    name: run_in_parallel
    steps:
      - type: query
        name: query1
        source: postgres
        query: "SELECT ..."
        output: result1
      
      - type: query
        name: query2
        source: postgres
        query: "SELECT ..."
        output: result2\n`;
                            setActionCodeOrQuery(actionCodeOrQuery + template);
                          }}
                          className="px-3 py-1.5 text-xs font-medium bg-pink-100 hover:bg-pink-200 text-pink-700 border border-pink-300 rounded-md transition-colors shadow-sm"
                          title="Insert Parallel step block"
                        >
                          + Parallel
                        </button>
                      </div>
                    )}
                  </div>
                  
                  <textarea
                    value={actionCodeOrQuery}
                    onChange={(e) => setActionCodeOrQuery(e.target.value)}
                    placeholder={
                      actionType === "data_query"
                        ? "SELECT * FROM users WHERE id = {user_id}"
                        : actionType === "data_pipeline"
                        ? `steps:
  # Parallel execution - both queries run simultaneously!
  - type: parallel
    name: fetch_all_financial_data
    steps:
      - type: query
        name: fetch_sales
        source: postgres
        credential_ref: postgres_aiven_cloud_db
        query: "SELECT * FROM sales WHERE date >= {start_date}"
        output: sales_data
      
      - type: query
        name: fetch_expenses
        source: postgres
        credential_ref: postgres_aiven_cloud_db
        query: "SELECT * FROM expenses WHERE date >= {start_date}"
        output: expense_data
  
  # Outputs are auto-merged! Both sales_data and expense_data available
  
  - type: skill
    name: llm_analysis
    skill: FinancialAnalyzer
    inputs: [sales_data, expense_data]
  
  - type: transform
    name: compute_metrics
    function: compute_financial_metrics
    inputs: [sales_data, expense_data]
    output: computed_metrics
  
  - type: transform
    name: format_report
    function: format_financial_report
    inputs: [computed_metrics]
    output: final_report`
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
                        Define multi-step pipeline with <code className="bg-gray-100 px-1 rounded">query</code>, <code className="bg-gray-100 px-1 rounded">transform</code>, <code className="bg-gray-100 px-1 rounded">skill</code>, <code className="bg-gray-100 px-1 rounded">merge</code>, and <code className="bg-gray-100 px-1 rounded">parallel</code> steps. Use parallel to run independent steps concurrently for better performance.
                      </>
                    )}
                  </p>
                </div>
                
                {/* Pipeline Functions Editor (only for data_pipeline) */}
                {actionType === "data_pipeline" && (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-900 mb-2">
                      Pipeline Functions (Python)
                      <span className="ml-2 text-xs text-gray-500 font-normal">
                        Optional - Define functions used in transform steps
                      </span>
                    </label>
                    <textarea
                      value={pipelineFunctions}
                      onChange={(e) => setPipelineFunctions(e.target.value)}
                      placeholder={`# Define functions called by transform steps
# Example:

def compute_financial_metrics(sales_data, expense_data):
    """Calculate financial metrics from raw data."""
    total_revenue = sum(row['total_revenue'] for row in sales_data['query_result'])
    total_expenses = sum(row['total_expense'] for row in expense_data['query_result'])
    
    return {
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'gross_profit': total_revenue - total_expenses,
        'profit_margin': (total_revenue - total_expenses) / total_revenue if total_revenue > 0 else 0
    }


def format_financial_report(computed_metrics):
    """Format metrics into a readable report."""
    return {
        'report_type': 'Financial Analysis',
        'metrics': {
            'revenue': f"$\\{computed_metrics['total_revenue']:,.2f}",
            'expenses': f"$\\{computed_metrics['total_expenses']:,.2f}",
            'profit': f"$\\{computed_metrics['gross_profit']:,.2f}",
            'margin': f"{computed_metrics['profit_margin']*100:.1f}%"
        }
    }`}
                      className="w-full h-64 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm bg-gray-900 text-gray-100"
                    />
                    <p className="text-xs text-gray-600 mt-2">
                      Write Python functions that will be called by <code className="bg-gray-100 px-1 rounded">type: transform</code> steps. 
                      Function names must match the <code className="bg-gray-100 px-1 rounded">function:</code> field in your pipeline steps.
                    </p>
                  </div>
                )}
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
