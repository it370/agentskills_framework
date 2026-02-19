"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import DashboardLayout from "@/components/DashboardLayout";
import ProtectedRoute from "@/components/ProtectedRoute";
import { isAgenticViewEnabled, updateAdminConfig } from "@/lib/api";

const AGENTIC_VIEW_KEY = "feature.agentic_view_enabled";

export default function AdminConfigPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [agenticViewEnabled, setAgenticViewEnabled] = useState(true);

  useEffect(() => {
    if (!user?.is_admin) {
      router.push("/");
      return;
    }
    let cancelled = false;
    (async () => {
      const enabled = await isAgenticViewEnabled();
      if (!cancelled) {
        setAgenticViewEnabled(enabled);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, router]);

  async function toggleAgenticView() {
    const nextValue = !agenticViewEnabled;
    setSaving(true);
    try {
      await updateAdminConfig(
        AGENTIC_VIEW_KEY,
        { enabled: nextValue },
        "Enable/disable Agentic View tab and rendering"
      );
      setAgenticViewEnabled(nextValue);
    } catch (error) {
      console.error("Failed to update agentic view config", error);
      alert("Failed to update configuration");
    } finally {
      setSaving(false);
    }
  }

  if (!user?.is_admin) return null;

  return (
    <ProtectedRoute>
      <DashboardLayout>
        <div className="p-6 max-w-4xl">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900">Configuration</h1>
            <p className="text-gray-600 mt-1">Admin feature controls for runtime UI behavior</p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-gray-900">Agentic View</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Controls visibility of the Agentic View tab for run details.
                </p>
              </div>
              <button
                type="button"
                onClick={toggleAgenticView}
                disabled={loading || saving}
                className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium transition ${
                  agenticViewEnabled
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                    : "bg-gray-100 text-gray-700 border border-gray-300"
                } disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {loading ? "Loading..." : saving ? "Saving..." : agenticViewEnabled ? "Enabled" : "Disabled"}
              </button>
            </div>
          </div>
        </div>
      </DashboardLayout>
    </ProtectedRoute>
  );
}
