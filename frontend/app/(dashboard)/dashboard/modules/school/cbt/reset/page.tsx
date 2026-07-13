"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cbtApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { toast } from "sonner";
import { ArrowLeft, RotateCcw, Loader2, AlertTriangle } from "lucide-react";

export default function CbtResetPage() {
  const canWrite = useHasPermission("school:write");
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["cbt-exams"], queryFn: () => cbtApi.exams.list() });
  const exams: any[] = Array.isArray(data) ? data : (data?.items ?? []);
  const [examId, setExamId] = useState("");

  const reset = useMutation({
    mutationFn: (id: string) => cbtApi.exams.reset(id),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ["cbt-results"] });
      toast.success(`${res?.reset ?? 0} attempt(s) reset — the class can retake.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Reset failed."),
  });

  const exam = exams.find((e) => e.id === examId);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">CBT Reset</h1>
      <p className="text-slate-500 text-sm mb-6">Reset every attempt on a test so the whole class can retake it.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="label">Test</label>
          <select value={examId} onChange={(e) => setExamId(e.target.value)} className="input">
            <option value="">Select a test…</option>
            {exams.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        </div>

        <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Attempts aren&apos;t deleted — they&apos;re <strong>superseded</strong> (kept for the record, badged, and dropped from stats), which frees each student&apos;s slot to retake. This can&apos;t be undone from here.</span>
        </div>

        {canWrite ? (
          <button
            onClick={() => { if (examId && confirm(`Reset ALL attempts on "${exam?.title}"? Every student can then retake.`)) reset.mutate(examId); }}
            disabled={!examId || reset.isPending}
            className="btn-primary gap-2 bg-rose-600 hover:bg-rose-700"
          >
            {reset.isPending ? <Loader2 size={15} className="animate-spin" /> : <RotateCcw size={15} />} Reset all attempts
          </button>
        ) : <p className="text-sm text-slate-400">You don&apos;t have permission to reset.</p>}
      </div>
    </div>
  );
}
