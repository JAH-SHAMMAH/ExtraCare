"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, XCircle, Loader2, RefreshCw, ExternalLink, Download, Clock, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { ImportPreset, BulkCommitResult } from "@/lib/import/presets";
import type { ValidationResult } from "@/lib/import/validator";
import { downloadCSV } from "@/lib/import/templates";
import { importApi } from "@/lib/api";

interface CommitStepProps<T> {
  preset: ImportPreset<T>;
  validation: ValidationResult<T>;
  result: BulkCommitResult | null;
  setResult: (r: BulkCommitResult) => void;
  onReset: () => void;
  filename?: string;
  duplicateStrategy?: "skip" | "overwrite";
}

interface BackendRecord {
  id: string;
  entity: string;
  filename: string;
  status: string;
  created: number;
  failed: number;
  duration_ms: number;
  total_rows: number;
  valid_rows: number;
  skipped_invalid: number;
  skipped_duplicate: number;
  user_email: string;
  created_at: string;
  created_ids?: string[];
  error_details?: Array<{ row: number; error: string; data: unknown }>;
}

/** Threshold above which we offload import to a background server-side job */
const BACKGROUND_THRESHOLD = 1000;
/** Polling interval for background job status (ms) */
const POLL_INTERVAL_MS = 1500;

export function CommitStep<T>({ preset, validation, result, setResult, onReset, filename, duplicateStrategy }: CommitStepProps<T>) {
  const [progress, setProgress] = useState({ processed: 0, total: validation.valid.length });
  const [isRunning, setIsRunning] = useState(false);
  const [started, setStarted] = useState(false);
  const [backendRecord, setBackendRecord] = useState<BackendRecord | null>(null);
  const [mode, setMode] = useState<"foreground" | "background">("foreground");
  const startTime = useRef(0);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const useBackground = validation.valid.length >= BACKGROUND_THRESHOLD;

  useEffect(() => {
    if (started || result) return;
    setStarted(true);
    setIsRunning(true);
    startTime.current = performance.now();
    setMode(useBackground ? "background" : "foreground");

    const rows = validation.valid.map((r) => r.data);

    if (useBackground) {
      runBackgroundImport(rows as Record<string, unknown>[]);
    } else {
      runForegroundImport(rows);
    }

    return () => {
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runForegroundImport = async (rows: T[]) => {
    try {
      const res = await preset.bulkCreate(rows, (p) => setProgress(p));
      setResult(res);
      const durationMs = Math.round(performance.now() - startTime.current);

      // Record to backend import history
      try {
        const record = await importApi.create({
          entity: preset.entity,
          filename: filename || "unknown.csv",
          total_rows: validation.valid.length + validation.invalid.length,
          valid_rows: validation.valid.length,
          created: res.created,
          failed: res.failed.length,
          skipped_invalid: validation.invalid.length,
          skipped_duplicate: validation.duplicates?.length || 0,
          duration_ms: durationMs,
          created_ids: res.createdIds || [],
          error_details: res.failed.slice(0, 100),
          duplicate_strategy: duplicateStrategy || "skip",
        });
        setBackendRecord(record);
      } catch {
        // Backend recording failed — non-critical
      }

      if (res.failed.length === 0) {
        toast.success(`Imported ${res.created} ${preset.entity} successfully.`);
      } else {
        toast.warning(`Imported ${res.created} of ${rows.length}. ${res.failed.length} failed.`);
      }
    } catch (e) {
      toast.error((e as Error).message || "Import failed");
    } finally {
      setIsRunning(false);
    }
  };

  const runBackgroundImport = async (rows: Record<string, unknown>[]) => {
    try {
      const job: BackendRecord = await importApi.startBackground({
        entity: preset.entity,
        filename: filename || "unknown.csv",
        rows,
        skipped_invalid: validation.invalid.length,
        skipped_duplicate: validation.duplicates?.length || 0,
        duplicate_strategy: duplicateStrategy || "skip",
      });
      setBackendRecord(job);
      toast.info(`Background import started — ${rows.length} rows queued.`);
      pollJobStatus(job.id);
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || (e as Error).message
        || "Failed to start background import";
      toast.error(msg);
      setIsRunning(false);
    }
  };

  const pollJobStatus = (jobId: string) => {
    const tick = async () => {
      try {
        const job: BackendRecord = await importApi.get(jobId);
        setBackendRecord(job);
        setProgress({ processed: job.created + job.failed, total: job.total_rows });

        if (job.status === "processing") {
          pollTimer.current = setTimeout(tick, POLL_INTERVAL_MS);
        } else {
          // Terminal state — synthesize a BulkCommitResult for the receipt UI
          setResult({
            created: job.created,
            failed: (job.error_details || []).map((e) => ({
              row: e.row,
              error: e.error,
              data: e.data,
            })),
            createdIds: job.created_ids || [],
          });
          setIsRunning(false);
          if (job.status === "completed") {
            toast.success(`Imported ${job.created} ${preset.entity} successfully.`);
          } else if (job.status === "partially_completed") {
            toast.warning(`Imported ${job.created} of ${job.total_rows}. ${job.failed} failed.`);
          } else {
            toast.error(`Import failed. ${job.failed} errors.`);
          }
        }
      } catch {
        // Transient poll failure — retry once more, then give up
        pollTimer.current = setTimeout(tick, POLL_INTERVAL_MS * 2);
      }
    };
    tick();
  };

  const percent = progress.total > 0 ? Math.round((progress.processed / progress.total) * 100) : 0;

  const handleDownloadFailures = () => {
    if (!result) return;
    const header = "row,error";
    const lines = result.failed.map((f) => `"${f.row}","${f.error.replace(/"/g, '""')}"`);
    downloadCSV(`${preset.entity}-import-failures.csv`, [header, ...lines].join("\n"));
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    const s = (ms / 1000).toFixed(1);
    return `${s}s`;
  };

  const durationMs = backendRecord?.duration_ms || (result ? Math.round(performance.now() - startTime.current) : 0);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-8">
      {isRunning && !result && (
        <div className="max-w-xl mx-auto text-center">
          <Loader2 size={40} className="mx-auto text-brand-500 animate-spin mb-4" />
          <h2 className="text-lg font-bold text-slate-800">Importing {preset.entity}...</h2>
          {mode === "background" && (
            <div className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-1 rounded-full">
              <Zap size={11} />
              Background mode — server-side processing
            </div>
          )}
          <p className="text-xs text-slate-500 mt-2">
            Processed {progress.processed} of {progress.total}
          </p>
          <div className="mt-4 h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all duration-300"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400 mt-3">
            {mode === "background"
              ? "Safe to navigate away — the import will continue on the server."
              : "Please don't close this window while importing."}
          </p>
        </div>
      )}

      {result && (
        <div className="max-w-xl mx-auto">
          <div className="text-center mb-6">
            {result.failed.length === 0 ? (
              <>
                <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle2 size={32} className="text-emerald-600" />
                </div>
                <h2 className="text-xl font-black text-slate-900">Import Complete</h2>
                <p className="text-sm text-slate-500 mt-1">
                  Successfully imported {result.created} {preset.entity}.
                </p>
              </>
            ) : (
              <>
                <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
                  <XCircle size={32} className="text-amber-600" />
                </div>
                <h2 className="text-xl font-black text-slate-900">Partially Imported</h2>
                <p className="text-sm text-slate-500 mt-1">
                  Imported {result.created} successfully. {result.failed.length} row(s) failed.
                </p>
              </>
            )}
          </div>

          {/* Summary grid */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-700 mb-1">Created</p>
              <p className="text-2xl font-black text-emerald-800">{result.created}</p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-red-700 mb-1">Failed</p>
              <p className="text-2xl font-black text-red-800">{result.failed.length}</p>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1 flex items-center gap-1">
                <Clock size={10} /> Duration
              </p>
              <p className="text-2xl font-black text-slate-700">{formatDuration(durationMs)}</p>
            </div>
          </div>

          {/* Import receipt */}
          <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-lg">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-2">
              Import Receipt
              {mode === "background" && (
                <span className="inline-flex items-center gap-1 text-[9px] text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded font-bold">
                  <Zap size={9} /> BACKGROUND
                </span>
              )}
            </p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
              <p className="text-slate-500">File</p>
              <p className="text-slate-800 font-medium truncate">{filename || "unknown.csv"}</p>
              <p className="text-slate-500">Entity</p>
              <p className="text-slate-800 font-medium capitalize">{preset.entity}</p>
              <p className="text-slate-500">Total rows in file</p>
              <p className="text-slate-800 font-medium">{validation.valid.length + validation.invalid.length}</p>
              <p className="text-slate-500">Passed validation</p>
              <p className="text-slate-800 font-medium">{validation.valid.length}</p>
              <p className="text-slate-500">Skipped (invalid)</p>
              <p className="text-slate-800 font-medium">{validation.invalid.length}</p>
              <p className="text-slate-500">Created in DB</p>
              <p className="text-emerald-700 font-bold">{result.created}</p>
              <p className="text-slate-500">Failed at backend</p>
              <p className={cn("font-bold", result.failed.length > 0 ? "text-red-700" : "text-slate-400")}>{result.failed.length}</p>
              {backendRecord && (
                <>
                  <p className="text-slate-500">Imported by</p>
                  <p className="text-slate-800 font-medium">{backendRecord.user_email}</p>
                  <p className="text-slate-500">Timestamp</p>
                  <p className="text-slate-800 font-medium">{new Date(backendRecord.created_at).toLocaleString()}</p>
                  <p className="text-slate-500">Import ID</p>
                  <p className="text-slate-500 font-mono text-[10px]">{backendRecord.id}</p>
                </>
              )}
            </div>
          </div>

          {/* Failure details */}
          {result.failed.length > 0 && (
            <div className="mb-6 border border-red-200 rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 bg-red-50 border-b border-red-200">
                <p className="text-xs font-bold text-red-800">Failed Rows</p>
                <button onClick={handleDownloadFailures} className="text-[11px] font-semibold text-red-700 hover:underline flex items-center gap-1">
                  <Download size={11} />
                  Download CSV
                </button>
              </div>
              <div className="max-h-48 overflow-auto">
                <table className="w-full text-left">
                  <thead className="bg-red-50/50">
                    <tr>
                      <th className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-red-700 w-16">Row</th>
                      <th className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-red-700">Error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-red-100">
                    {result.failed.map((f, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 text-xs text-slate-600 font-mono">{f.row}</td>
                        <td className="px-4 py-2 text-xs text-red-700">{f.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-center gap-3">
            <button onClick={onReset} className="btn-secondary gap-2">
              <RefreshCw size={14} />
              Import Another File
            </button>
            <Link href={preset.listRoute} className="btn-primary gap-2">
              View {preset.entity}
              <ExternalLink size={14} />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
