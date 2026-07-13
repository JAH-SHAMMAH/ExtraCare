"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation } from "@tanstack/react-query";
import { cbtApi } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, Download, Loader2 } from "lucide-react";

export default function CbtExportPage() {
  const { data } = useQuery({ queryKey: ["cbt-exams"], queryFn: () => cbtApi.exams.list() });
  const exams: any[] = Array.isArray(data) ? data : (data?.items ?? []);
  const [examId, setExamId] = useState("");

  const exp = useMutation({
    mutationFn: (id: string) => cbtApi.results.exportCsv(id),
    onSuccess: (blob: Blob, id) => {
      const exam = exams.find((e) => e.id === id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cbt-results-${(exam?.title || "exam").replace(/\s+/g, "-")}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Results exported.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Export failed."),
  });

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">CBT Test Export</h1>
      <p className="text-slate-500 text-sm mb-6">Download a test&apos;s results as a CSV.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-6 flex flex-col sm:flex-row sm:items-end gap-4">
        <div className="flex-1">
          <label className="label">Test</label>
          <select value={examId} onChange={(e) => setExamId(e.target.value)} className="input">
            <option value="">Select a test…</option>
            {exams.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        </div>
        <button onClick={() => examId && exp.mutate(examId)} disabled={!examId || exp.isPending} className="btn-primary gap-2">
          {exp.isPending ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Export CSV
        </button>
      </div>
    </div>
  );
}
