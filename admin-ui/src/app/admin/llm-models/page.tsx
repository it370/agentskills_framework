"use client";

import { useEffect, useMemo, useState } from "react";
import DashboardLayout from "../../../components/DashboardLayout";
import { useAuth } from "../../../contexts/AuthContext";
import {
  createLlmModel,
  deleteLlmModel,
  fetchLlmModels,
  LlmModelOption,
  updateLlmModel,
} from "../../../lib/api";

type EditableModel = LlmModelOption & {
  api_key?: string;
};

export default function LlmModelsAdminPage() {
  const { user, loading } = useAuth();
  const [models, setModels] = useState<LlmModelOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [operationMessage, setOperationMessage] = useState<string>("");

  const [newModel, setNewModel] = useState({
    provider: "",
    model_name: "",
    api_key: "",
    is_active: true,
    is_default: false,
  });

  const isSystemUser = user?.username === "system";

  const loadModels = async () => {
    setError(null);
    setLoadingModels(true);
    setOperationMessage("Loading models...");
    try {
      const data = await fetchLlmModels(true);
      setModels(data);
    } catch (err: any) {
      setError(err.message || "Failed to load models");
    } finally {
      setLoadingModels(false);
      setOperationMessage("");
    }
  };

  useEffect(() => {
    if (!loading && isSystemUser) {
      loadModels();
    }
  }, [loading, isSystemUser]);

  const handleCreate = async () => {
    setError(null);
    setSaving(true);
    setOperationMessage("Creating model...");
    try {
      if (!newModel.model_name.trim() || !newModel.provider.trim() || !newModel.api_key.trim()) {
        throw new Error("Provider, model name, and API key are required");
      }
      await createLlmModel({
        provider: newModel.provider.trim(),
        model_name: newModel.model_name.trim(),
        api_key: newModel.api_key.trim(),
        is_active: newModel.is_active,
        is_default: newModel.is_default,
      });
      setNewModel({
        provider: "",
        model_name: "",
        api_key: "",
        is_active: true,
        is_default: false,
      });
      setOperationMessage("Refreshing list...");
      await loadModels();
    } catch (err: any) {
      setError(err.message || "Failed to create model");
    } finally {
      setSaving(false);
      setOperationMessage("");
    }
  };

  const handleUpdate = async (model: EditableModel) => {
    setError(null);
    setSaving(true);
    setOperationMessage(`Updating ${model.model_name}...`);
    try {
      await updateLlmModel(model.model_name, {
        provider: model.provider,
        api_key: model.api_key?.trim() ? model.api_key.trim() : undefined,
        is_active: model.is_active,
        is_default: model.is_default,
      });
      setOperationMessage("Refreshing list...");
      await loadModels();
    } catch (err: any) {
      setError(err.message || "Failed to update model");
    } finally {
      setSaving(false);
      setOperationMessage("");
    }
  };

  const handleDelete = async (modelName: string) => {
    if (!confirm(`Delete model '${modelName}'? This cannot be undone.`)) {
      return;
    }
    setError(null);
    setSaving(true);
    setOperationMessage(`Deleting ${modelName}...`);
    try {
      await deleteLlmModel(modelName);
      setOperationMessage("Refreshing list...");
      await loadModels();
    } catch (err: any) {
      setError(err.message || "Failed to delete model");
    } finally {
      setSaving(false);
      setOperationMessage("");
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

  if (!isSystemUser) {
    return (
      <DashboardLayout>
        <div className="p-8">
          <div className="rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-800">System user access required.</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">LLM Models</h1>
          <p className="mt-2 text-sm text-gray-600">
            Manage supported models and API keys. Only available for the system user.
          </p>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Add Model</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <input
                value={newModel.provider}
                onChange={(e) => setNewModel({ ...newModel, provider: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                placeholder="openai"
                disabled={saving || loadingModels}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Name</label>
              <input
                value={newModel.model_name}
                onChange={(e) => setNewModel({ ...newModel, model_name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                placeholder="gpt-4o-mini"
                disabled={saving || loadingModels}
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input
                type="password"
                value={newModel.api_key}
                onChange={(e) => setNewModel({ ...newModel, api_key: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                placeholder="sk-..."
                disabled={saving || loadingModels}
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={newModel.is_active}
                  onChange={(e) => setNewModel({ ...newModel, is_active: e.target.checked })}
                  disabled={saving || loadingModels}
                />
                Active
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={newModel.is_default}
                  onChange={(e) => setNewModel({ ...newModel, is_default: e.target.checked })}
                  disabled={saving || loadingModels}
                />
                Default
              </label>
            </div>
          </div>
          <button
            onClick={handleCreate}
            disabled={saving || loadingModels}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Add Model"}
          </button>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Existing Models</h2>
          {loadingModels && models.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-sm text-gray-600">Loading models...</span>
            </div>
          ) : models.length === 0 ? (
            <p className="text-sm text-gray-600">No models configured.</p>
          ) : (
            <div className="space-y-4">
              {models.map((model) => (
                <ModelRow
                  key={model.model_name}
                  model={model}
                  onSave={handleUpdate}
                  onDelete={handleDelete}
                  saving={saving}
                  disabled={loadingModels}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Loading Overlay */}
      {(saving || loadingModels) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 shadow-xl flex flex-col items-center space-y-4 min-w-[300px]">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-900">
                {operationMessage || "Processing..."}
              </p>
              <p className="text-sm text-gray-600 mt-1">Please wait</p>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

function ModelRow({
  model,
  onSave,
  onDelete,
  saving,
  disabled,
}: {
  model: LlmModelOption;
  onSave: (model: EditableModel) => void;
  onDelete: (modelName: string) => void;
  saving: boolean;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState<EditableModel>({ ...model, api_key: "" });
  const isDisabled = saving || disabled;

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-3">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Provider</label>
          <input
            value={draft.provider || ""}
            onChange={(e) => setDraft({ ...draft, provider: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
            disabled={isDisabled}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Model Name</label>
          <input
            value={draft.model_name || ""}
            disabled
            className="w-full px-3 py-2 border border-gray-200 rounded bg-gray-50 text-sm"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">API Key (leave blank to keep)</label>
        <input
          type="password"
          value={draft.api_key || ""}
          onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
          disabled={isDisabled}
        />
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={!!draft.is_active}
            onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
            disabled={isDisabled}
          />
          Active
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={!!draft.is_default}
            onChange={(e) => setDraft({ ...draft, is_default: e.target.checked })}
            disabled={isDisabled}
          />
          Default
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => onSave(draft)}
          disabled={isDisabled}
          className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Save
        </button>
        <button
          onClick={() => onDelete(draft.model_name)}
          disabled={isDisabled}
          className="px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
