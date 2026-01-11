"use client";

import { useEffect, useState } from "react";
import CodeEditor from "@uiw/react-textarea-code-editor";

interface PythonEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minHeight?: string;
  disabled?: boolean;
  className?: string;
  onValidation?: (isValid: boolean, error?: string) => void;
}

export default function PythonEditor({
  value,
  onChange,
  placeholder = "# Write your Python code here...",
  minHeight = "300px",
  disabled = false,
  className = "",
  onValidation,
}: PythonEditorProps) {
  const [error, setError] = useState<string | null>(null);

  // Validate Python syntax using Skulpt (client-side Python parser)
  useEffect(() => {
    if (!value.trim()) {
      setError(null);
      onValidation?.(true);
      return;
    }

    const validateSyntax = async () => {
      try {
        // Use dynamic import to avoid SSR issues
        const Sk = await import("skulpt");
        
        Sk.default.configure({
          output: () => {}, // Suppress output
          read: () => "", // No file reading
        });

        // Try to parse the code
        Sk.default.importMainWithBody("<stdin>", false, value, true);
        
        setError(null);
        onValidation?.(true);
      } catch (e: any) {
        const errorMsg = e.toString();
        setError(errorMsg);
        onValidation?.(false, errorMsg);
      }
    };

    const debounce = setTimeout(validateSyntax, 500);
    return () => clearTimeout(debounce);
  }, [value, onValidation]);

  return (
    <div className={`relative ${className}`}>
      <CodeEditor
        value={value}
        language="python"
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        padding={15}
        style={{
          fontSize: 13,
          backgroundColor: "#1e1e1e",
          fontFamily:
            'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
          minHeight: minHeight,
          borderRadius: "0.5rem",
          border: error ? "2px solid #ef4444" : "1px solid #374151",
        }}
        data-color-mode="dark"
      />
      {error && (
        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">Python Syntax Error</p>
              <p className="text-xs text-red-700 mt-1 font-mono">{error}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
