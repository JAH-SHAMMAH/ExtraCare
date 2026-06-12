"use client";

import { Fragment, useState, useMemo, useEffect } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, XCircle, AlertTriangle, Download, ChevronDown, ChevronRight, Loader2, Database } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ImportPreset } from "@/lib/import/presets";
import type { ValidationResult } from "@/lib/import/validator";
import { buildErrorsCSV } from "@/lib/import/validator";
import { downloadCSV } from "@/lib/import/templates";
import { importApi } from "@/lib/api";

interface PreviewStepProps<T> {
  preset: ImportPreset<T>;
  validation: ValidationResult<T>;
  onBack: () => void;
  onCommit: (validation: ValidationResult<T>) => void;
  duplicateStrategy?: "skip" | "overwrite";
  onDuplicateStrategyChange?: (s: "skip" | "overwrite") => void;
}

type Tab = "all" | "valid" | "invalid";

/** Detect which field to use for server-side duplicate checking per entity */
function getDuplicateField(entity: string): { field: string; label: string } | null {
  switch (entity) {
    case "students": return { field: "email", label: "email" };
    case "patients": return { field: "email", label: "email" };
    case "employees": return { field: "email", label: "email" };
    case "inventory": return { field: "sku", label: "SKU" };
    case "transactions": return { field: "reference", label: "reference" };
    default: return null;
  }
}

export function PreviewStep<T>({ preset, validation, onBack, onCommit, duplicateStrategy = "skip", onDuplicateStrategyChange }: PreviewStepProps<T>) {
  const [skipInvalid, setSkipInvalid] = useState(false);
  const [tab, setTab] = useState<Tab>(validation.invalid.length > 0 ? "invalid" : "all");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [serverDuplicates, setServerDuplicates] = useState<string[]>([]);
  const [checkingDuplicates, setCheckingDuplicates] = useState(false);
  const [duplicatesChecked, setDuplicatesChecked] = useState(false);

  const totalRows = validation.valid.length + validation.invalid.length;
  const hasErrors = validation.invalid.length > 0;
  const canProceed = !hasErrors || skipInvalid;

  // Check for server-side duplicates on mount
  const dupConfig = getDuplicateField(preset.entity);
  useEffect(() => {
    if (!dupConfig) return;
    const values = validation.valid
      .map((r) => {
        const d = r.data as Record<string, unknown>;
        return d[dupConfig.field];
      })
      .filter((v): v is string => typeof v === "string" && v.length > 0);

    if (values.length === 0) {
      setDuplicatesChecked(true);
      return;
    }

    setCheckingDuplicates(true);
    importApi
      .checkDuplicates({ entity: preset.entity, field: dupConfig.field, values })
      .then((res) => {
        setServerDuplicates(res.duplicates || []);
      })
      .catch(() => {
        // Non-critical — proceed without duplicate info
      })
      .finally(() => {
        setCheckingDuplicates(false);
        setDuplicatesChecked(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownloadErrors = () => {
    downloadCSV(`${preset.entity}-errors.csv`, buildErrorsCSV(validation.invalid));
  };

  // Error summary: group by field -> count
  const errorSummary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const row of validation.invalid) {
      for (const field of Object.keys(row.errors)) {
        counts[field] = (counts[field] || 0) + 1;
      }
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([field, count]) => {
        const col = preset.columns.find((c) => c.key === field);
        return { field, label: col?.label || field, count };
      });
  }, [validation.invalid, preset.columns]);

  // Merged view
  const mergedRows = [
    ...validation.valid.map((r) => ({ ...r, status: "valid" as const })),
    ...validation.invalid.map((r) => ({ rowNumber: r.rowNumber, data: r.raw, errors: r.errors, status: "invalid" as const })),
  ].sort((a, b) => a.rowNumber - b.rowNumber);

  const rowsToShow =
    tab === "all" ? mergedRows : tab === "valid" ? mergedRows.filter((r) => r.status === "valid") : mergedRows.filter((r) => r.status === "invalid");

  // Show up to 8 columns in the table
  const visibleColumns = preset.columns.slice(0, 8);

  // Lowercased Set for O(1) duplicate lookup. Used both to count server-side
  // duplicates in the summary and to mark individual rows in the table.
  const serverDupSet = useMemo(
    () => new Set(serverDuplicates.map((v) => v.toLowerCase())),
    [serverDuplicates]
  );

  const isServerDuplicate = (data: Record<string, unknown>): boolean => {
    if (!dupConfig) return false;
    const val = data[dupConfig.field];
    return typeof val === "string" && serverDupSet.has(val.toLowerCase());
  };

  const serverDupCount = useMemo(
    () => (dupConfig ? validation.valid.filter((r) => isServerDuplicate(r.data as Record<string, unknown>)).length : 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [validation.valid, serverDupSet, dupConfig]
  );

  const effectiveValidCount = duplicateStrategy === "skip" ? validation.valid.length - serverDupCount : validation.valid.length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="p-6 border-b border-slate-100">
        <h2 className="text-base font-bold text-slate-800 mb-1">Preview & Validate</h2>
        <p className="text-xs text-slate-500">Review rows before committing. Click an invalid row to see all field errors.</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 p-6 border-b border-slate-100 bg-slate-50/50">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Total Rows</p>
          <p className="text-2xl font-black text-slate-900">{totalRows}</p>
        </div>
        <div className="bg-white rounded-lg border border-emerald-200 p-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 mb-1 flex items-center gap-1">
            <CheckCircle2 size={11} /> Valid
          </p>
          <p className="text-2xl font-black text-emerald-700">{validation.valid.length}</p>
        </div>
        <div className={cn("bg-white rounded-lg border p-4", hasErrors ? "border-red-200" : "border-slate-200")}>
          <p className={cn("text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1", hasErrors ? "text-red-600" : "text-slate-500")}>
            <XCircle size={11} /> Invalid
          </p>
          <p className={cn("text-2xl font-black", hasErrors ? "text-red-700" : "text-slate-400")}>{validation.invalid.length}</p>
        </div>
      </div>

      {/* Server-side duplicate detection panel */}
      {dupConfig && (
        <div className="mx-6 mt-6">
          {checkingDuplicates ? (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2 text-xs text-blue-700">
              <Loader2 size={14} className="animate-spin" />
              Checking for existing {dupConfig.label} duplicates in database...
            </div>
          ) : serverDupCount > 0 ? (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-start gap-2 mb-3">
                <Database size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-amber-800">
                  <p className="font-semibold">{serverDupCount} record(s) already exist in the database (matched by {dupConfig.label})</p>
                  <p className="text-amber-700 mt-0.5">
                    Choose how to handle these duplicates:
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4 ml-5">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="dupStrategy"
                    checked={duplicateStrategy === "skip"}
                    onChange={() => onDuplicateStrategyChange?.("skip")}
                    className="accent-brand-600"
                  />
                  <span className="text-xs font-medium text-slate-700">Skip duplicates</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="dupStrategy"
                    checked={duplicateStrategy === "overwrite"}
                    onChange={() => onDuplicateStrategyChange?.("overwrite")}
                    className="accent-brand-600"
                  />
                  <span className="text-xs font-medium text-slate-700">Overwrite existing</span>
                </label>
              </div>
              {serverDuplicates.length <= 10 && (
                <div className="mt-2 ml-5 flex flex-wrap gap-1">
                  {serverDuplicates.map((v) => (
                    <span key={v} className="text-[10px] px-2 py-0.5 bg-amber-100 text-amber-800 rounded font-mono">{v}</span>
                  ))}
                </div>
              )}
            </div>
          ) : duplicatesChecked ? (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-xs text-emerald-700">
              <CheckCircle2 size={14} />
              No existing duplicates found in database (checked by {dupConfig.label}).
            </div>
          ) : null}
        </div>
      )}

      {/* Error summary panel */}
      {hasErrors && errorSummary.length > 0 && (
        <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs font-bold text-red-800 mb-2 flex items-center gap-1.5">
            <XCircle size={13} />
            Error Breakdown — {validation.invalid.length} row(s) have issues
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {errorSummary.map((e) => (
              <div key={e.field} className="flex items-center justify-between bg-white border border-red-100 rounded px-3 py-1.5">
                <span className="text-xs font-medium text-slate-700">{e.label}</span>
                <span className="text-[10px] font-bold text-red-700 bg-red-100 px-1.5 py-0.5 rounded ml-2">
                  {e.count} error{e.count > 1 ? "s" : ""}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-red-700 mt-2">
            Fix these fields in your source file, or enable &quot;Skip invalid rows&quot; below to import the valid ones.
          </p>
        </div>
      )}

      {validation.duplicates.length > 0 && (
        <div className="mx-6 mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2">
          <AlertTriangle size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-amber-800">
            <p className="font-semibold">{validation.duplicates.length} in-file duplicate(s) detected</p>
            <p className="text-amber-700 mt-0.5">
              Duplicate emails found — only the first occurrence will be imported.
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-slate-100 mt-4">
        <div className="flex items-center gap-1">
          {(["all", "valid", "invalid"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-colors",
                tab === t ? "bg-brand-50 text-brand-700" : "text-slate-500 hover:bg-slate-100"
              )}
            >
              {t} ({t === "all" ? totalRows : t === "valid" ? validation.valid.length : validation.invalid.length})
            </button>
          ))}
        </div>
        {hasErrors && (
          <button onClick={handleDownloadErrors} className="btn-secondary gap-1.5 text-xs">
            <Download size={12} />
            Download Errors CSV
          </button>
        )}
      </div>

      {/* Table */}
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 sticky top-0 z-10">
            <tr>
              <th className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-500 w-10"></th>
              <th className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-500 w-14">Row</th>
              <th className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-500 w-16">Status</th>
              {visibleColumns.map((c) => (
                <th key={c.key} className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {rowsToShow.slice(0, 500).map((row) => {
              const isInvalid = row.status === "invalid";
              const data = row.data as Record<string, unknown>;
              const errors = isInvalid ? (row as { errors: Record<string, string> }).errors : {};
              const errorCount = Object.keys(errors).length;
              const isExpanded = expandedRow === row.rowNumber && isInvalid;

              const isServerDup = !isInvalid && isServerDuplicate(data);

              return (
                <Fragment key={row.rowNumber}>
                  <tr
                    className={cn(
                      isInvalid && "bg-red-50/50 cursor-pointer hover:bg-red-50",
                      isServerDup && duplicateStrategy === "skip" && "bg-amber-50/50 opacity-60",
                      !isInvalid && !isServerDup && "hover:bg-slate-50/50"
                    )}
                    onClick={() => isInvalid && setExpandedRow(isExpanded ? null : row.rowNumber)}
                  >
                    <td className="px-3 py-2.5 text-slate-400">
                      {isInvalid ? (
                        isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-slate-500 font-mono">{row.rowNumber}</td>
                    <td className="px-3 py-2.5">
                      {isInvalid ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded">
                          <XCircle size={10} /> {errorCount}
                        </span>
                      ) : isServerDup && duplicateStrategy === "skip" ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                          <Database size={10} /> Dup
                        </span>
                      ) : isServerDup && duplicateStrategy === "overwrite" ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded">
                          <Database size={10} /> Update
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                          <CheckCircle2 size={10} /> OK
                        </span>
                      )}
                    </td>
                    {visibleColumns.map((c) => {
                      const fieldError = errors[c.key];
                      const value = data[c.key];
                      return (
                        <td
                          key={c.key}
                          className={cn("px-3 py-2.5 text-xs", fieldError ? "text-red-700" : "text-slate-700")}
                        >
                          <div className={cn("truncate max-w-[140px]", fieldError && "underline decoration-red-300 decoration-wavy underline-offset-2")}>
                            {value !== undefined && value !== null && value !== "" ? String(value) : <span className="text-slate-300">—</span>}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                  {/* Expanded error detail row */}
                  {isExpanded && (
                    <tr className="bg-red-50">
                      <td colSpan={visibleColumns.length + 3} className="px-6 py-3">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {Object.entries(errors).map(([field, message]) => {
                            const col = preset.columns.find((c) => c.key === field);
                            return (
                              <div key={field} className="flex items-start gap-2 bg-white border border-red-200 rounded-lg px-3 py-2">
                                <XCircle size={12} className="text-red-500 flex-shrink-0 mt-0.5" />
                                <div className="min-w-0">
                                  <p className="text-[10px] font-bold text-red-800 uppercase tracking-wider">{col?.label || field}</p>
                                  <p className="text-xs text-red-700 mt-0.5">{message}</p>
                                  {data[field] !== undefined && data[field] !== "" && (
                                    <p className="text-[10px] text-slate-500 mt-0.5">
                                      Value: <span className="font-mono">&quot;{String(data[field])}&quot;</span>
                                    </p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {rowsToShow.length > 500 && (
          <p className="px-4 py-3 text-[11px] text-slate-400 text-center border-t border-slate-100">
            Showing first 500 of {rowsToShow.length} rows. All rows will be processed on commit.
          </p>
        )}
      </div>

      {/* Footer actions */}
      <div className="p-6 border-t border-slate-100 bg-slate-50/50">
        {hasErrors && (
          <label className="flex items-start gap-2 mb-4 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={skipInvalid}
              onChange={(e) => setSkipInvalid(e.target.checked)}
              className="mt-0.5"
            />
            <div>
              <p className="text-xs font-semibold text-slate-700">
                Skip invalid rows and import the {validation.valid.length} valid one(s)
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Off by default. We recommend fixing errors in your source file first — download the errors CSV above for a fix list.
              </p>
            </div>
          </label>
        )}

        <div className="flex items-center justify-between">
          <button onClick={onBack} className="btn-secondary gap-2">
            <ArrowLeft size={14} />
            Back to Mapping
          </button>
          <button
            onClick={() => onCommit(validation)}
            disabled={!canProceed || validation.valid.length === 0 || checkingDuplicates}
            className="btn-primary gap-2"
          >
            {checkingDuplicates ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Checking...
              </>
            ) : (
              <>
                Import {effectiveValidCount > 0 ? effectiveValidCount : validation.valid.length} Row{(effectiveValidCount > 0 ? effectiveValidCount : validation.valid.length) === 1 ? "" : "s"}
                <ArrowRight size={14} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
