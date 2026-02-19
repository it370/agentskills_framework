export type RunTemplateFieldType = "text" | "textarea" | "number" | "select" | "boolean";

export type RunTemplateField = {
  key: string;
  label: string;
  type: RunTemplateFieldType;
  required?: boolean;
  placeholder?: string;
  helpText?: string;
  defaultValue?: string | number | boolean;
  options?: Array<{ label: string; value: string }>;
};

export type RunTemplateBranding = {
  title?: string;
  subtitle?: string;
  accentColor?: string;
  logoUrl?: string;
};

export type RunTemplate = {
  id: string;
  name: string;
  description?: string;
  mode: "raw-json" | "form";
  autoApplyAll?: boolean;
  prefill?: {
    runName?: string;
    sop?: string;
    llmModel?: string;
  };
  branding?: RunTemplateBranding;
  fields?: RunTemplateField[];
  recommendedSop?: string;
};

export type RunTemplateAssignment = {
  templateId: string;
  workspaceId?: string;
  userId?: string;
  userGroup?: string;
};

export type RunTemplateContext = {
  workspaceId?: string | null;
  userId?: string | null;
  userGroups?: string[];
};

// NOTE: Hardcoded for now. Next step can source this from API/config.
const HARDCODED_TEMPLATES: RunTemplate[] = [
  {
    id: "raw-json-default",
    name: "Raw JSON (Default)",
    description: "Current behavior. Manually provide initial_data JSON.",
    mode: "raw-json",
  },
  // {
  //   id: "customer-order-intake-v1",
  //   name: "Customer Order Intake (v1)",
  //   description: "Example dynamic template with five required inputs.",
  //   mode: "form",
  //   recommendedSop:
  //     "Validate customer and order details, enrich with shipping checks, then continue workflow.",
  //   branding: {
  //     title: "Order Intake Assistant",
  //     subtitle: "Provide all mandatory fields to start this workflow.",
  //     accentColor: "#2563eb",
  //   },
  //   fields: [
  //     {
  //       key: "customer_id",
  //       label: "Customer ID",
  //       type: "text",
  //       required: true,
  //       placeholder: "CUS-100045",
  //     },
  //     {
  //       key: "order_number",
  //       label: "Order Number",
  //       type: "text",
  //       required: true,
  //       placeholder: "SO-2026-00031",
  //     },
  //     {
  //       key: "requested_date",
  //       label: "Requested Date",
  //       type: "text",
  //       required: true,
  //       placeholder: "2026-02-19",
  //       helpText: "Use ISO date format (YYYY-MM-DD).",
  //     },
  //     {
  //       key: "priority",
  //       label: "Priority",
  //       type: "select",
  //       required: true,
  //       defaultValue: "normal",
  //       options: [
  //         { label: "Low", value: "low" },
  //         { label: "Normal", value: "normal" },
  //         { label: "High", value: "high" },
  //         { label: "Critical", value: "critical" },
  //       ],
  //     },
  //     {
  //       key: "destination_country",
  //       label: "Destination Country",
  //       type: "text",
  //       required: true,
  //       placeholder: "USA",
  //     },
  //     {
  //       key: "include_fragile_handling",
  //       label: "Include Fragile Handling",
  //       type: "boolean",
  //       defaultValue: false,
  //     },
  //     {
  //       key: "notes",
  //       label: "Notes",
  //       type: "textarea",
  //       placeholder: "Any extra context for the run...",
  //     },
  //   ],
  // },
  {
    id: "flood-zone-analysis-v1",
    name: "Flood zone Analysis v1",
    description: "Geo-focused run template. Address is mandatory before run start.",
    mode: "form",
    autoApplyAll: true,
    prefill: {
      runName: "Flood Zone Analysis",
      sop: "For given address string, verify and extract lan parcel detail from reportall followed by determine flood zone with FEMA NFHL layer.",
      llmModel: "gpt-4.1",
    },
    branding: {
      title: "Flood Risk Analyzer",
      subtitle: "Address is required to begin this workflow.",
      accentColor: "#0e7490",
    },
    fields: [
      {
        key: "raw_address",
        label: "Address Details",
        helpText: "Try full formatted address string when available. Natural Language input is also accepted.",
        type: "text",
        required: true,
        placeholder: "221B Baker Street, London",
      },
      // {
      //   key: "country",
      //   label: "Country",
      //   type: "text",
      //   placeholder: "United Kingdom",
      // },
      // {
      //   key: "analysis_depth",
      //   label: "Analysis Depth",
      //   type: "select",
      //   defaultValue: "standard",
      //   options: [
      //     { label: "Fast", value: "fast" },
      //     { label: "Standard", value: "standard" },
      //     { label: "Detailed", value: "detailed" },
      //   ],
      // },
    ],
  },
];

// NOTE: Hardcoded assignment rules for now. Replace with runtime rules later.
const HARDCODED_ASSIGNMENTS: RunTemplateAssignment[] = [];

function matchesAssignment(
  assignment: RunTemplateAssignment,
  context: RunTemplateContext
): boolean {
  if (assignment.workspaceId && assignment.workspaceId !== context.workspaceId) return false;
  if (assignment.userId && assignment.userId !== context.userId) return false;
  if (assignment.userGroup) {
    if (!context.userGroups || !context.userGroups.includes(assignment.userGroup)) return false;
  }
  return true;
}

export function resolveAssignedTemplateId(context: RunTemplateContext): string {
  const matched = HARDCODED_ASSIGNMENTS.find((rule) => matchesAssignment(rule, context));
  return matched?.templateId || "raw-json-default";
}

export function getRunTemplates(): RunTemplate[] {
  return HARDCODED_TEMPLATES;
}

export function getRunTemplateById(templateId: string): RunTemplate | undefined {
  return HARDCODED_TEMPLATES.find((template) => template.id === templateId);
}

export function createTemplateInitialValues(template: RunTemplate): Record<string, string> {
  const values: Record<string, string> = {};
  if (!template.fields) return values;
  for (const field of template.fields) {
    if (field.defaultValue === undefined || field.defaultValue === null) {
      values[field.key] = "";
      continue;
    }
    values[field.key] = String(field.defaultValue);
  }
  return values;
}

function coerceFieldValue(field: RunTemplateField, rawValue: string): unknown {
  if (field.type === "number") {
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) ? parsed : rawValue;
  }
  if (field.type === "boolean") {
    if (rawValue === "true") return true;
    if (rawValue === "false") return false;
  }
  return rawValue;
}

export function buildInitialDataFromTemplate(
  template: RunTemplate,
  values: Record<string, string>
): Record<string, unknown> {
  if (!template.fields) return {};
  const output: Record<string, unknown> = {};
  for (const field of template.fields) {
    const rawValue = values[field.key] ?? "";
    const trimmed = typeof rawValue === "string" ? rawValue.trim() : rawValue;
    if (trimmed === "") continue;
    output[field.key] = coerceFieldValue(field, rawValue);
  }
  return output;
}

export function validateTemplateValues(
  template: RunTemplate,
  values: Record<string, string>
): string[] {
  if (!template.fields) return [];
  const errors: string[] = [];
  for (const field of template.fields) {
    if (!field.required) continue;
    const rawValue = values[field.key];
    if (rawValue === undefined || rawValue === null || rawValue.toString().trim() === "") {
      errors.push(`${field.label} is required.`);
    }
  }
  return errors;
}
