"use client";

import DashboardLayout from "../../components/DashboardLayout";

export default function WorkflowsPage() {
  return (
    <DashboardLayout>
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Workflows</h1>
          <p className="mt-2 text-sm text-gray-600">
            Visual workflow builder and editor (coming soon)
          </p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-16 text-center">
          <svg
            className="mx-auto h-16 w-16 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M4 5a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 17a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1v-2zM14 17a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1h-4a1 1 0 01-1-1v-2z"
            />
          </svg>
          <h3 className="mt-4 text-lg font-semibold text-gray-900">
            Visual Workflow Editor
          </h3>
          <p className="mt-2 text-sm text-gray-600 max-w-md mx-auto">
            Drag-and-drop workflow creation, skill orchestration, and graph visualization will be available here.
          </p>
          <div className="mt-6">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg text-sm text-gray-700">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Coming Soon
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

