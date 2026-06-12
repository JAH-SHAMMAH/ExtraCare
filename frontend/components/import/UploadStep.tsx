"use client";

import { useRef, useState } from "react";
import { Upload, FileText, Download, Loader2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { parseCSV, type ParsedFile, MAX_FILE_SIZE_BYTES, MAX_ROWS } from "@/lib/import/parsers";
import { autoMapHeaders } from "@/lib/import/validator";
import { buildTemplateCSV, downloadCSV } from "@/lib/import/templates";
import type { ImportPreset } from "@/lib/import/presets";

interface UploadStepProps<T> {
  preset: ImportPreset<T>;
  onParsed: (file: ParsedFile, initialMapping: Record<string, string>, filename: string) => void;
}

export function UploadStep<T>({ preset, onParsed }: UploadStepProps<T>) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Only CSV files are supported. Export your Excel sheet as CSV and try again.");
      return;
    }
    setIsParsing(true);
    try {
      const parsed = await parseCSV(file);
      const initialMapping = autoMapHeaders(parsed.headers, preset.columns);
      toast.success(`Parsed ${parsed.rows.length} rows from ${file.name}`);
      onParsed(parsed, initialMapping, file.name);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsParsing(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const handleDownloadTemplate = () => {
    downloadCSV(`${preset.entity}-template.csv`, buildTemplateCSV(preset));
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-base font-bold text-slate-800">Upload CSV File</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Max {(MAX_FILE_SIZE_BYTES / 1024 / 1024)} MB · Max {MAX_ROWS.toLocaleString()} rows
            </p>
          </div>
          <button onClick={handleDownloadTemplate} className="btn-secondary gap-2 text-xs">
            <Download size={14} />
            Download Template
          </button>
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            isDragging ? "border-brand-500 bg-brand-50/50" : "border-slate-200 hover:border-brand-400 hover:bg-slate-50"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
          />
          {isParsing ? (
            <Loader2 size={32} className="mx-auto text-brand-500 animate-spin" />
          ) : (
            <Upload size={32} className="mx-auto text-slate-400" />
          )}
          <p className="mt-3 text-sm font-semibold text-slate-700">
            {isParsing ? "Parsing file..." : "Drop your CSV file here, or click to browse"}
          </p>
          <p className="text-xs text-slate-400 mt-1">.csv files only</p>
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle size={16} className="text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-700">{error}</p>
          </div>
        )}

        <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-100">
          <p className="text-xs font-bold text-slate-700 flex items-center gap-1.5 mb-2">
            <FileText size={13} />
            Expected columns
          </p>
          <div className="flex flex-wrap gap-1.5">
            {preset.columns.map((c) => (
              <span
                key={c.key}
                className="text-[10px] px-2 py-1 rounded-md bg-white border border-slate-200 text-slate-600 font-medium"
              >
                {c.label}
                {c.required && <span className="text-red-500 ml-0.5">*</span>}
              </span>
            ))}
          </div>
          <p className="text-[10px] text-slate-400 mt-2">
            Required fields are marked with <span className="text-red-500">*</span>. Missing optional columns are fine.
          </p>
        </div>
      </div>
    </div>
  );
}
