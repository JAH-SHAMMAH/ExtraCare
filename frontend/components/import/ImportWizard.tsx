"use client";

import { useState, useEffect } from "react";
import { Check, History, Clock, CheckCircle2, XCircle, ChevronDown, ChevronRight, Undo2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { ImportPreset, BulkCommitResult } from "@/lib/import/presets";
import type { ParsedFile } from "@/lib/import/parsers";
import type { ValidationResult } from "@/lib/import/validator";
import { importApi } from "@/lib/api";
import { UploadStep } from "./UploadStep";
import { MappingStep } from "./MappingStep";
import { PreviewStep } from "./PreviewStep";
import { CommitStep } from "./CommitStep";

interface ImportWizardProps<T> {
  preset: ImportPreset<T>;
}

type Step = "upload" | "map" | "preview" | "commit";

const STEPS: { id: Step; label: string }[] = [
  { id: "upload", label: "Upload" },
  { id: "map", label: "Map Columns" },
  { id: "preview", label: "Preview" },
  { id: "commit", label: "Import" },
];

export interface ImportJobRecord {
  id: string;
  entity: string;
  filename: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  created: number;
  failed: number;
  skipped_invalid: number;
  skipped_duplicate: number;
  duration_ms: number;
  created_ids: string[];
  error_details: Array<{ row: number; error: string; data: unknown }>;
  user_email: string;
  duplicate_strategy: string;
  created_at: string;
}

export function ImportWizard<T>({ preset }: ImportWizardProps<T>) {
  const [step, setStep] = useState<Step>("upload");
  const [parsed, setParsed] = useState<ParsedFile | null>(null);
  const [filename, setFilename] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<ValidationResult<T> | null>(null);
  const [result, setResult] = useState<BulkCommitResult | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<ImportJobRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [duplicateStrategy, setDuplicateStrategy] = useState<"skip" | "overwrite">("skip");

  const loadHistory = async () => {
    try {
      setLoadingHistory(true);
      const res = await importApi.list({ entity: preset.entity, page_size: 20 });
      setHistory(res.items || []);
    } catch {
      // Silently fail — history is non-critical
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Load history on mount and after each import
  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset.entity, result]);

  const currentIndex = STEPS.findIndex((s) => s.id === step);

  const handleParsed = (file: ParsedFile, initialMapping: Record<string, string>, name: string) => {
    setParsed(file);
    setMapping(initialMapping);
    setFilename(name);
    setStep("map");
  };

  const handleMappingConfirmed = (finalMapping: Record<string, string>, finalValidation: ValidationResult<T>) => {
    setMapping(finalMapping);
    setValidation(finalValidation);
    setStep("preview");
  };

  const handleCommit = (finalValidation: ValidationResult<T>) => {
    setValidation(finalValidation);
    setStep("commit");
  };

  const handleReset = () => {
    setStep("upload");
    setParsed(null);
    setFilename("");
    setMapping({});
    setValidation(null);
    setResult(null);
  };

  const handleRollback = async (jobId: string) => {
    if (!confirm("Are you sure you want to undo this import? All created records will be soft-deleted.")) return;
    setRollingBack(jobId);
    try {
      const res = await importApi.rollback(jobId);
      toast.success(`Rolled back ${res.rolled_back} records.`);
      await loadHistory();
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Rollback failed";
      toast.error(msg);
    } finally {
      setRollingBack(null);
    }
  };

  const statusColor = (s: string) => {
    if (s === "completed") return "text-emerald-700 bg-emerald-50";
    if (s === "partially_completed") return "text-amber-700 bg-amber-50";
    if (s === "rolled_back") return "text-slate-500 bg-slate-100 line-through";
    return "text-red-700 bg-red-50";
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between mb-8">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span className="capitalize">{preset.entity === "students" ? "School" : preset.entity === "patients" ? "Hospital" : "Business"}</span>
            <span>/</span>
            <span className="capitalize">{preset.entity}</span>
            <span>/</span>
            <span className="text-brand-600 font-semibold">Import</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">{preset.label}</h1>
          <p className="text-slate-500 text-sm mt-0.5">{preset.description}</p>
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="btn-secondary gap-1.5 text-xs flex-shrink-0"
        >
          <History size={13} />
          History
          {showHistory ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>
      </div>

      {/* Import history panel (backend-backed) */}
      {showHistory && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <p className="text-xs font-bold text-slate-700 mb-3 flex items-center gap-1.5">
            <History size={13} /> Import History
          </p>
          {loadingHistory ? (
            <div className="flex items-center gap-2 py-4 justify-center text-slate-400">
              <Loader2 size={16} className="animate-spin" /> Loading...
            </div>
          ) : history.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-4">No imports yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {history.map((h) => (
                <div key={h.id} className="flex items-center justify-between py-2.5 gap-4">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-800 truncate">{h.filename}</p>
                    <p className="text-[10px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                      <Clock size={10} />
                      {new Date(h.created_at).toLocaleDateString()} {new Date(h.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      {h.user_email && <span className="text-slate-300">by {h.user_email}</span>}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded", statusColor(h.status))}>
                      {h.status.replace("_", " ")}
                    </span>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded flex items-center gap-1">
                      <CheckCircle2 size={10} /> {h.created}
                    </span>
                    {h.failed > 0 && (
                      <span className="text-[10px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded flex items-center gap-1">
                        <XCircle size={10} /> {h.failed}
                      </span>
                    )}
                    <span className="text-[10px] text-slate-400">{h.total_rows} rows</span>
                    {(h.status === "completed" || h.status === "partially_completed") && h.created_ids.length > 0 && (
                      <button
                        onClick={() => handleRollback(h.id)}
                        disabled={rollingBack === h.id}
                        className="text-[10px] font-semibold text-red-600 hover:text-red-800 flex items-center gap-0.5 disabled:opacity-50"
                        title="Undo this import"
                      >
                        {rollingBack === h.id ? <Loader2 size={10} className="animate-spin" /> : <Undo2 size={10} />}
                        Undo
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step indicator */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
        <ol className="flex items-center gap-2">
          {STEPS.map((s, i) => {
            const isComplete = i < currentIndex;
            const isActive = i === currentIndex;
            return (
              <li key={s.id} className="flex items-center gap-2 flex-1">
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-colors",
                    isComplete
                      ? "bg-emerald-500 text-white"
                      : isActive
                        ? "bg-brand-600 text-white"
                        : "bg-slate-100 text-slate-400"
                  )}
                >
                  {isComplete ? <Check size={14} /> : i + 1}
                </div>
                <div className="flex-1">
                  <p
                    className={cn(
                      "text-xs font-semibold",
                      isActive ? "text-slate-900" : isComplete ? "text-slate-600" : "text-slate-400"
                    )}
                  >
                    {s.label}
                  </p>
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={cn(
                      "h-0.5 flex-1 mx-2 transition-colors",
                      isComplete ? "bg-emerald-500" : "bg-slate-200"
                    )}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </div>

      {/* Step body */}
      {step === "upload" && <UploadStep preset={preset} onParsed={handleParsed} />}
      {step === "map" && parsed && (
        <MappingStep
          preset={preset}
          parsed={parsed}
          initialMapping={mapping}
          onBack={() => setStep("upload")}
          onConfirmed={handleMappingConfirmed}
        />
      )}
      {step === "preview" && parsed && validation && (
        <PreviewStep
          preset={preset}
          validation={validation}
          onBack={() => setStep("map")}
          onCommit={handleCommit}
          duplicateStrategy={duplicateStrategy}
          onDuplicateStrategyChange={setDuplicateStrategy}
        />
      )}
      {step === "commit" && validation && (
        <CommitStep
          preset={preset}
          validation={validation}
          result={result}
          setResult={setResult}
          onReset={handleReset}
          filename={filename}
          duplicateStrategy={duplicateStrategy}
        />
      )}
    </div>
  );
}
