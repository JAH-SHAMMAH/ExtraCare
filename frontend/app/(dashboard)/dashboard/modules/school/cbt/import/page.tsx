"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { cbtApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { toast } from "sonner";
import { ArrowLeft, Upload, Loader2, FileUp, CheckCircle2, AlertTriangle } from "lucide-react";

export default function CbtImportPage() {
  const canWrite = useHasPermission("school:write");
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<{ imported: number; errors?: string[] } | null>(null);

  const imp = useMutation({
    mutationFn: (file: File) => cbtApi.bank.import(file),
    onSuccess: (res: any) => { setResult(res); toast.success(`Imported ${res?.imported ?? 0} question(s).`); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Import failed."),
  });

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) imp.mutate(f);
    e.target.value = "";
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/modules/school/cbt/question-bank" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Question Bank</Link>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">CBT Import</h1>
      <p className="text-slate-500 text-sm mb-6">Bulk-import questions into the Question Bank from a CSV.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 mb-5">
          <p className="font-semibold text-slate-700 mb-1">CSV columns (case-insensitive):</p>
          <code className="text-[11px] break-words">question, type, subject, topic, difficulty, option_a…option_e, correct_answer, points</code>
          <p className="mt-1.5 text-slate-400">Unknown subject / type / difficulty fall back to null / mcq / medium.</p>
        </div>

        {canWrite ? (
          <>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={onFile} />
            <button onClick={() => fileRef.current?.click()} disabled={imp.isPending} className="btn-primary gap-2">
              {imp.isPending ? <Loader2 size={15} className="animate-spin" /> : <FileUp size={15} />} Choose CSV & import
            </button>
          </>
        ) : <p className="text-sm text-slate-400">You don&apos;t have permission to import.</p>}

        {result && (
          <div className="mt-5 space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700"><CheckCircle2 size={16} /> {result.imported} question(s) imported.</div>
            {result.errors && result.errors.length > 0 && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                <p className="font-semibold flex items-center gap-1.5 mb-1"><AlertTriangle size={13} /> {result.errors.length} row(s) skipped:</p>
                <ul className="list-disc pl-5 space-y-0.5">{result.errors.slice(0, 12).map((er, i) => <li key={i}>{er}</li>)}</ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
