"use client";

import { useState, useMemo } from "react";
import { ArrowLeft, ArrowRight, AlertCircle, Loader2 } from "lucide-react";
import type { ImportPreset } from "@/lib/import/presets";
import type { ParsedFile } from "@/lib/import/parsers";
import { validateRowsAsync, type ValidationResult } from "@/lib/import/validator";

interface MappingStepProps<T> {
  preset: ImportPreset<T>;
  parsed: ParsedFile;
  initialMapping: Record<string, string>;
  onBack: () => void;
  onConfirmed: (mapping: Record<string, string>, validation: ValidationResult<T>) => void;
}

export function MappingStep<T>({ preset, parsed, initialMapping, onBack, onConfirmed }: MappingStepProps<T>) {
  const [mapping, setMapping] = useState<Record<string, string>>(initialMapping);
  const [isValidating, setIsValidating] = useState(false);
  const [progress, setProgress] = useState({ processed: 0, total: parsed.rows.length });

  const missingRequired = useMemo(
    () => preset.columns.filter((c) => c.required && !mapping[c.key]),
    [preset.columns, mapping]
  );

  const handleContinue = async () => {
    setIsValidating(true);
    setProgress({ processed: 0, total: parsed.rows.length });
    try {
      const validation = await validateRowsAsync(
        preset.schema,
        parsed.rows,
        mapping,
        preset.columns,
        (processed, total) => setProgress({ processed, total })
      );
      onConfirmed(mapping, validation);
    } finally {
      setIsValidating(false);
    }
  };

  const percent = progress.total > 0 ? Math.round((progress.processed / progress.total) * 100) : 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="mb-5">
        <h2 className="text-base font-bold text-slate-800">Map Columns</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Confirm how your CSV columns map to {preset.entity} fields. We&apos;ve auto-matched where possible.
        </p>
      </div>

      {parsed.warnings.length > 0 && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-xs font-bold text-amber-800 mb-1 flex items-center gap-1.5">
            <AlertCircle size={13} /> Parser warnings
          </p>
          <ul className="text-[11px] text-amber-700 space-y-0.5">
            {parsed.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <div className="divide-y divide-slate-100 border border-slate-100 rounded-lg">
        {preset.columns.map((col) => (
          <div key={col.key} className="grid grid-cols-2 gap-4 p-4 items-center">
            <div>
              <label className="text-sm font-semibold text-slate-700">
                {col.label}
                {col.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <p className="text-[11px] text-slate-400 mt-0.5">Example: {col.example || "—"}</p>
            </div>
            <select
              value={mapping[col.key] || ""}
              onChange={(e) => setMapping((prev) => ({ ...prev, [col.key]: e.target.value }))}
              disabled={isValidating}
              className="input text-sm"
            >
              <option value="">— Skip this field —</option>
              {parsed.headers.map((h) => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {missingRequired.length > 0 && (
        <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-700">
            Required fields not mapped: <span className="font-semibold">{missingRequired.map((c) => c.label).join(", ")}</span>
          </p>
        </div>
      )}

      {isValidating && (
        <div className="mt-4 p-4 bg-brand-50/50 border border-brand-100 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 size={14} className="text-brand-600 animate-spin" />
            <p className="text-xs font-semibold text-brand-700">
              Validating {progress.processed.toLocaleString()} of {progress.total.toLocaleString()} rows...
            </p>
          </div>
          <div className="h-1.5 bg-white rounded-full overflow-hidden">
            <div className="h-full bg-brand-500 transition-all duration-200" style={{ width: `${percent}%` }} />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mt-6">
        <button onClick={onBack} disabled={isValidating} className="btn-secondary gap-2">
          <ArrowLeft size={14} />
          Back
        </button>
        <button
          onClick={handleContinue}
          disabled={missingRequired.length > 0 || isValidating}
          className="btn-primary gap-2"
        >
          {isValidating ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Validating...
            </>
          ) : (
            <>
              Validate & Preview
              <ArrowRight size={14} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
