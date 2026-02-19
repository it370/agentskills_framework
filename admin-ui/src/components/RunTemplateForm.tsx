"use client";

import { RunTemplate } from "../lib/runTemplates";

type RunTemplateFormProps = {
  template: RunTemplate;
  values: Record<string, string>;
  errors: string[];
  onChange: (fieldKey: string, value: string) => void;
};

export default function RunTemplateForm({ template, values, errors, onChange }: RunTemplateFormProps) {
  if (template.mode !== "form" || !template.fields || template.fields.length === 0) {
    return null;
  }

  const accent = template.branding?.accentColor || "#2563eb";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-5">
      {(template.branding?.title || template.branding?.subtitle) && (
        <div className="rounded-lg border px-4 py-3" style={{ borderColor: `${accent}55`, backgroundColor: `${accent}11` }}>
          <div className="flex items-center gap-3">
            {template.branding?.logoUrl ? (
              <img src={template.branding.logoUrl} alt="template-logo" className="h-10 w-10 rounded object-contain bg-white border border-gray-200 p-1" />
            ) : (
              <div className="h-10 w-10 rounded text-white text-xs font-semibold flex items-center justify-center" style={{ backgroundColor: accent }}>
                RUN
              </div>
            )}
            <div>
              {template.branding?.title && <p className="text-sm font-semibold text-gray-900">{template.branding.title}</p>}
              {template.branding?.subtitle && <p className="text-xs text-gray-600 mt-0.5">{template.branding.subtitle}</p>}
            </div>
          </div>
        </div>
      )}

      {errors.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2">
          <p className="text-xs font-semibold text-red-800 mb-1">Required fields missing</p>
          <ul className="text-xs text-red-700 list-disc ml-4 space-y-0.5">
            {errors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {template.fields.map((field) => {
          const value = values[field.key] ?? "";
          const isLong = field.type === "textarea";
          return (
            <div key={field.key} className={isLong ? "md:col-span-2" : ""}>
              <label className="block mb-1.5">
                <span className="text-sm font-medium text-gray-900">
                  {field.label}{" "}
                  {field.required ? <span className="text-red-500">*</span> : <span className="text-gray-400 font-normal">(Optional)</span>}
                </span>
                {field.helpText ? <p className="mt-1 text-xs text-gray-600">{field.helpText}</p> : null}
              </label>

              {field.type === "textarea" ? (
                <textarea
                  value={value}
                  onChange={(e) => onChange(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full h-24 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              ) : field.type === "select" ? (
                <select
                  value={value}
                  onChange={(e) => onChange(field.key, e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">Select...</option>
                  {(field.options || []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.type === "boolean" ? (
                <select
                  value={value}
                  onChange={(e) => onChange(field.key, e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">Select...</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              ) : (
                <input
                  type={field.type === "number" ? "number" : "text"}
                  value={value}
                  onChange={(e) => onChange(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
