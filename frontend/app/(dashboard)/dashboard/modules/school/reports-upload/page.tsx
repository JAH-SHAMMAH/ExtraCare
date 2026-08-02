"use client";

import { useRef, useState } from "react";
import { useTerms, useReportUpload } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { Loader2, Upload, FileSpreadsheet, CheckCircle2, AlertTriangle } from "lucide-react";

export default function ReportsUploadPage() {
  const canWrite = useHasPermission("school:reports:write");
  const { data: terms = [] } = useTerms();
  const [termId, setTermId] = useState("");
  const upload = useReportUpload();
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<any>(null);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !termId) return;
    const fd = new FormData();
    fd.append("file", file);
    upload.mutate({ term_id: termId, formData: fd }, { onSuccess: (r) => setResult(r) });
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Secondary School Report</span><span>/</span><span className="text-brand-600 font-semibold">Reports Upload</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><FileSpreadsheet size={22} className="text-brand-600" /> Reports Upload</h1>
      <p className="text-slate-500 text-sm mb-5">Import assessment scores in bulk from a spreadsheet instead of typing them one by one.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="label">Term</label>
          <select value={termId} onChange={(e) => setTermId(e.target.value)} className="input max-w-xs">
            <option value="">— Select the term —</option>
            {(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>

        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-5 text-sm text-slate-600">
          <p className="font-semibold text-slate-700 mb-1">Expected columns (case-insensitive)</p>
          <p><b>student</b> (full name) or <b>admission_no</b>, <b>subject</b>, then one column per assessment — for example <b>CBT, THEORY, PRJ, PBT, EXAM</b>. Each row is one pupil in one subject.</p>
          <p className="text-xs text-slate-400 mt-2">Accepts CSV, Excel (.xlsx), Word or PDF (with a table). Assessment column names must match those set up under Report Setup → Assessment for the chosen term. Re-uploading updates existing scores.</p>
        </div>

        {canWrite ? (
          <div>
            <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.docx,.pdf" onChange={onFile} disabled={!termId} className="hidden" />
            <button onClick={() => fileRef.current?.click()} disabled={!termId || upload.isPending} className="btn-primary gap-2">
              {upload.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} Choose file & upload
            </button>
            {!termId && <span className="text-xs text-slate-400 ml-3">Select a term first.</span>}
          </div>
        ) : (
          <p className="text-sm text-slate-500">You don&apos;t have permission to upload scores.</p>
        )}
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mt-5">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={18} className="text-emerald-600" />
            <p className="text-sm font-bold text-slate-800">Imported {result.imported} of {result.rows} row(s)</p>
          </div>
          {result.errors?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 flex items-center gap-1.5 mb-1"><AlertTriangle size={13} /> {result.errors.length} row(s) skipped</p>
              <ul className="text-xs text-slate-500 list-disc pl-5 space-y-0.5 max-h-52 overflow-y-auto">
                {result.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
