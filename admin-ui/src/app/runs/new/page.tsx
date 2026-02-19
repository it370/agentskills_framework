"use client";

import { useState, useEffect, Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import DashboardLayout from "../../../components/DashboardLayout";
import RunTemplateForm from "../../../components/RunTemplateForm";
import { getAuthHeaders } from "../../../lib/auth";
import { fetchLlmModels, LlmModelOption } from "../../../lib/api";
import { getActiveWorkspaceId } from "../../../lib/workspaceStorage";
import {
  buildInitialDataFromTemplate,
  createTemplateInitialValues,
  getRunTemplateById,
  getRunTemplates,
  resolveAssignedTemplateId,
  validateTemplateValues,
} from "../../../lib/runTemplates";
import { useRun } from "../../../contexts/RunContext";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
function NewRunForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { initializeRun } = useRun();
  
  const [runName, setRunName] = useState("");
  const [sop, setSop] = useState(
    // "Retrieve order details of given order, if a valid company is obtained run through logbook to find the company's contact details."
    "Just execute Profiler Retriever, display result and end."
  );
  const [initialData, setInitialData] = useState("");  // Empty by default, use placeholder
  const [llmModel, setLlmModel] = useState("");
  const [llmOptions, setLlmOptions] = useState<LlmModelOption[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("raw-json-default");
  const [templateValues, setTemplateValues] = useState<Record<string, string>>({});
  const [templateErrors, setTemplateErrors] = useState<string[]>([]);
  const [templateTouched, setTemplateTouched] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ackUnsubscribe, setAckUnsubscribe] = useState<(() => void) | null>(null);
  const templates = getRunTemplates();
  const selectedTemplate = getRunTemplateById(selectedTemplateId) || templates[0];
  const currentTemplateValidationErrors = useMemo(() => {
    if (!selectedTemplate || selectedTemplate.mode !== "form") return [];
    return validateTemplateValues(selectedTemplate, templateValues);
  }, [selectedTemplate, templateValues]);
  const templateDisplayErrors = templateTouched
    ? (templateErrors.length > 0 ? templateErrors : currentTemplateValidationErrors)
    : [];
  const isStartDisabled =
    loading ||
    !sop.trim() ||
    (selectedTemplate?.mode === "form" && currentTemplateValidationErrors.length > 0);

  // Pre-populate from sessionStorage (for Edit and Rerun) or query params (legacy)
  useEffect(() => {
    // Check sessionStorage first
    const storedConfig = sessionStorage.getItem('rerun_config');
    if (storedConfig) {
      try {
        const config = JSON.parse(storedConfig);
        if (config.runName) setRunName(config.runName);
        if (config.sop) setSop(config.sop);
        if (config.initialData) {
          setInitialData(JSON.stringify(config.initialData, null, 2));
        }
        // For llmModel, set it even if empty string (user can clear to use server default)
        if (config.llmModel !== undefined && config.llmModel !== null) {
          setLlmModel(config.llmModel);
        }
        // Clear after reading
        sessionStorage.removeItem('rerun_config');
        return;
      } catch (err) {
        console.error("Failed to parse stored rerun config:", err);
      }
    }
    
    // Fallback to URL params (legacy support)
    const paramRunName = searchParams.get('runName');
    const paramSop = searchParams.get('sop');
    const paramInitialData = searchParams.get('initialData');
    
    if (paramRunName) setRunName(paramRunName);
    if (paramSop) setSop(paramSop);
    if (paramInitialData) {
      try {
        // Parse and re-format to ensure valid JSON
        const parsed = JSON.parse(paramInitialData);
        setInitialData(JSON.stringify(parsed, null, 2));
      } catch {
        setInitialData(paramInitialData);
      }
    }
  }, [searchParams]);

  useEffect(() => {
    const workspaceId = getActiveWorkspaceId();
    const assignedTemplateId = resolveAssignedTemplateId({
      workspaceId,
      userId: null,
      userGroups: [],
    });
    setSelectedTemplateId(assignedTemplateId);
  }, []);

  useEffect(() => {
    if (!selectedTemplate || selectedTemplate.mode !== "form") {
      setTemplateValues({});
      setTemplateErrors([]);
      setTemplateTouched(false);
      setShowTemplateModal(false);
      return;
    }
    setTemplateValues(createTemplateInitialValues(selectedTemplate));
    setTemplateErrors([]);
    setTemplateTouched(false);
    setShowTemplateModal(true);
  }, [selectedTemplateId, selectedTemplate]);

  useEffect(() => {
    if (!selectedTemplate || !selectedTemplate.autoApplyAll || !selectedTemplate.prefill) return;
    if (selectedTemplate.prefill.runName !== undefined) setRunName(selectedTemplate.prefill.runName);
    if (selectedTemplate.prefill.sop !== undefined) setSop(selectedTemplate.prefill.sop);
    if (selectedTemplate.prefill.llmModel !== undefined) setLlmModel(selectedTemplate.prefill.llmModel);
  }, [selectedTemplate]);

  // Cleanup ACK listener on unmount
  useEffect(() => {
    return () => {
      if (ackUnsubscribe) {
        console.log("[NewRun] Component unmounting, cleaning up ACK listener");
        ackUnsubscribe();
      }
    };
  }, [ackUnsubscribe]);

  useEffect(() => {
    let cancelled = false;
    const loadModels = async () => {
      try {
        const models = await fetchLlmModels();
        if (!cancelled) {
          setLlmOptions(models);
        }
      } catch (err) {
        console.warn("[NewRun] Failed to load LLM models:", err);
      }
    };
    loadModels();
    return () => {
      cancelled = true;
    };
  }, []);

  const generateThreadId = () => {
    if (typeof window !== "undefined" && window.crypto?.randomUUID) {
      return `thread_${window.crypto.randomUUID()}`;
    }
    return `thread_${Date.now()}`;
  };

  const handleTemplateFieldChange = (fieldKey: string, value: string) => {
    const nextValues = { ...templateValues, [fieldKey]: value };
    setTemplateTouched(true);
    setTemplateValues(nextValues);
    if (selectedTemplate?.mode === "form") {
      setTemplateErrors(validateTemplateValues(selectedTemplate, nextValues));
    } else if (templateErrors.length > 0) {
      setTemplateErrors([]);
    }
  };

  const handleStart = async () => {
    setError(null);
    setLoading(true);

    let parsedData: Record<string, unknown> = {};
    if (selectedTemplate?.mode === "form") {
      const validationErrors = validateTemplateValues(selectedTemplate, templateValues);
      if (validationErrors.length > 0) {
        setTemplateTouched(true);
        setTemplateErrors(validationErrors);
        setError("Please complete all required template fields before starting.");
        setShowTemplateModal(true);
        setLoading(false);
        return;
      }
      parsedData = buildInitialDataFromTemplate(selectedTemplate, templateValues);
      setInitialData(JSON.stringify(parsedData, null, 2));
    } else {
      try {
        // Allow empty string - treat as empty object
        if (!initialData.trim()) {
          parsedData = {};
        } else {
          parsedData = JSON.parse(initialData);
        }
      } catch (e) {
        setError("Initial Data must be valid JSON");
        setLoading(false);
        return;
      }
    }

    const threadId = generateThreadId();
    const ackKey = `ack_${crypto.randomUUID()}`;
    console.log("[NewRun] Starting thread:", threadId, "with ack_key:", ackKey);

    // Initialize run in Redux store
    await initializeRun(threadId, {
      sop,
      initialData: parsedData,
      runName: runName.trim() || undefined,
      llmModel: llmModel.trim() || undefined,
    });

    // Subscribe to ACK event via global event bus
    const { adminEvents } = await import("../../../lib/adminEvents");
    
    const unsubscribe = adminEvents.once('ack', (event: any) => {
      if (event.ack_key === ackKey) {
        console.log("[NewRun] ✅ ACK received! Redirecting to thread page...");
        setAckUnsubscribe(null);  // Clear reference since we're done
        // Use Next.js router for client-side navigation (preserves console logs)
        router.push(`/admin/${threadId}`);
      }
    });
    
    // Store unsubscribe function so it can be cleaned up on unmount
    setAckUnsubscribe(() => unsubscribe);

    try {
      const response = await fetch(`${API_BASE}/start`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        },
        body: JSON.stringify({
          thread_id: threadId,
          sop: sop,
          initial_data: parsedData,
          run_name: runName.trim() || undefined,
          ack_key: ackKey,  // Send ACK key
          llm_model: llmModel.trim() || undefined,
          broadcast: true,  // Enable real-time broadcasts for UI
        }),
      });

      console.log("[NewRun] Response status:", response.status);

      if (!response.ok) {
        unsubscribe();  // Clean up listener on error
        setAckUnsubscribe(null);
        const errorText = await response.text();
        throw new Error(`Start failed: ${response.status} - ${errorText}`);
      }

      // Response received, waiting for ACK via global SSE admin stream
      const result = await response.json();
      console.log("[NewRun] HTTP response received:", result, "- waiting for ACK...");
      
    } catch (err: any) {
      console.error("[NewRun] Error:", err);
      setError(err.message || "Failed to start run");
      setLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="mb-6 max-w-4xl">
          <Link
            href="/"
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
            Back to Runs
          </Link>
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-3xl font-bold text-gray-900">
              {searchParams.get('from') === 'rerun' ? 'Edit and Rerun' : 'Start New Run'}
            </h1>
            <button
              onClick={handleStart}
              disabled={isStartDisabled}
              className="shrink-0 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2.5 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin h-4 w-4"
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
                  Starting...
                </>
              ) : (
                <>
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
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  Start Run
                </>
              )}
            </button>
          </div>
          <p className="mt-2 text-sm text-gray-600">
            {searchParams.get('from') === 'rerun'
              ? 'Modify the configuration below and start a new run'
              : 'Configure and launch a new workflow execution'}
          </p>
        </div>

        {/* Error Alert */}
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
              <h3 className="text-sm font-medium text-red-800">
                Failed to start run
              </h3>
              <p className="mt-1 text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Form */}
        <div className="max-w-4xl space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <label className="block mb-2">
              <span className="text-sm font-medium text-gray-900">
                Run Input Template
              </span>
              <p className="mt-1 text-xs text-gray-600">
                Default stays as raw JSON. Templates can be assigned dynamically by workspace/user/group later.
              </p>
            </label>
            <select
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
            {selectedTemplate?.description && (
              <p className="mt-2 text-xs text-gray-600">{selectedTemplate.description}</p>
            )}
            {selectedTemplate?.autoApplyAll && (
              <p className="mt-1 text-xs text-emerald-700">
                Template auto-apply is enabled: run name, SOP, and model are prefilled.
              </p>
            )}
            {selectedTemplate?.mode === "form" && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
                <p className="text-xs text-blue-800">
                  Fill variable inputs in a popup form.
                </p>
                <button
                  type="button"
                  onClick={() => setShowTemplateModal(true)}
                  className="text-xs font-medium text-blue-700 hover:text-blue-800"
                >
                  Open Input Form
                </button>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <label className="block mb-2">
              <span className="text-sm font-medium text-gray-900">
                Run Name (Optional)
              </span>
              <p className="mt-1 text-xs text-gray-600">
                A human-friendly name for this run. Defaults to thread ID if not provided.
              </p>
            </label>
            <input
              type="text"
              value={runName}
              onChange={(e) => setRunName(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="e.g., Order Processing for Customer XYZ"
            />
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <label className="block mb-2">
              <span className="text-sm font-medium text-gray-900">
                Workflow Instructions (Layman SOP)
              </span>
              <p className="mt-1 text-xs text-gray-600">
                Describe the workflow logic in plain language
              </p>
            </label>
            <textarea
              value={sop}
              onChange={(e) => setSop(e.target.value)}
              className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              placeholder="Enter workflow instructions..."
            />
            {selectedTemplate?.recommendedSop && (
              <button
                type="button"
                onClick={() => setSop(selectedTemplate.recommendedSop || "")}
                className="mt-2 text-xs text-blue-600 hover:text-blue-700"
              >
                Use template-recommended SOP
              </button>
            )}
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <label className="block mb-2">
              <span className="text-sm font-medium text-gray-900">
                LLM Model <span className="text-gray-500 font-normal">(Optional)</span>
              </span>
              <p className="mt-1 text-xs text-gray-600">
                Leave blank to inherit the server default model.
              </p>
            </label>
            <input
              list="llm-model-options"
              type="text"
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 text-sm ${
                llmModel && llmOptions.length > 0 && !llmOptions.some(m => m.model_name === llmModel)
                  ? 'border-red-300 focus:ring-red-500 bg-red-50'
                  : 'border-gray-300 focus:ring-blue-500'
              }`}
              placeholder="e.g., gpt-4o-mini"
            />
            <datalist id="llm-model-options">
              {llmOptions.map((model) => (
                <option key={model.model_name} value={model.model_name} />
              ))}
            </datalist>
            {llmModel && llmOptions.length > 0 && !llmOptions.some(m => m.model_name === llmModel) && (
              <p className="mt-1 text-xs text-red-600">
                ⚠️ Warning: "{llmModel}" is not in the list of configured models. Available models: {llmOptions.map(m => m.model_name).join(', ')}
              </p>
            )}
          </div>

          {selectedTemplate?.mode !== "form" && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <label className="block mb-2">
                <span className="text-sm font-medium text-gray-900">
                  Initial Data (JSON) <span className="text-gray-500 font-normal">(Optional)</span>
                </span>
                <p className="mt-1 text-xs text-gray-600">
                  Provide the starting data for the workflow. Leave empty if not needed.
                </p>
              </label>
              <textarea
                value={initialData}
                onChange={(e) => setInitialData(e.target.value)}
                className="w-full h-64 px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                spellCheck={false}
                placeholder='{ "order_number": "00000003" }'
              />
            </div>
          )}

          {selectedTemplate?.mode === "form" && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <label className="block mb-2">
                <span className="text-sm font-medium text-gray-900">Generated Initial Data (Preview)</span>
                <p className="mt-1 text-xs text-gray-600">
                  Populated from template input popup.
                </p>
              </label>
              <pre className="w-full h-64 px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg overflow-auto font-mono text-sm">
                {JSON.stringify(buildInitialDataFromTemplate(selectedTemplate, templateValues), null, 2)}
              </pre>
            </div>
          )}

          <div className="flex gap-4">
            <button
              onClick={handleStart}
              disabled={isStartDisabled}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin h-5 w-5"
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
                  Starting...
                </>
              ) : (
                <>
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
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  Start Run
                </>
              )}
            </button>
            <Link
              href="/"
              className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition-colors flex items-center justify-center"
            >
              Cancel
            </Link>
          </div>
        </div>
      </div>
      {selectedTemplate?.mode === "form" && showTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-3xl max-h-[90vh] overflow-hidden rounded-xl bg-white shadow-2xl border border-gray-200">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Template Inputs</h3>
                <p className="text-xs text-gray-600 mt-0.5">{selectedTemplate.name}</p>
              </div>
              <button
                type="button"
                onClick={() => setShowTemplateModal(false)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Close
              </button>
            </div>
            <div className="overflow-y-auto max-h-[calc(90vh-120px)] p-5">
              <RunTemplateForm
                template={selectedTemplate}
                values={templateValues}
                errors={templateDisplayErrors}
                onChange={handleTemplateFieldChange}
              />
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-gray-200 px-5 py-3">
              <button
                type="button"
                onClick={() => setShowTemplateModal(false)}
                disabled={currentTemplateValidationErrors.length > 0}
                className="px-3 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default function NewRunPage() {
  return (
    <Suspense fallback={
      <DashboardLayout>
        <div className="flex items-center justify-center h-screen">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
        </div>
      </DashboardLayout>
    }>
      <NewRunForm />
    </Suspense>
  );
}

