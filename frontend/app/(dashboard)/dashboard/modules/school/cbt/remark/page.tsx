"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cbtApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Save, MessageSquare } from "lucide-react";

export default function CbtRemarkPage() {
  const canWrite = useHasPermission("school:write");
  const { data: examData } = useQuery({ queryKey: ["cbt-exams"], queryFn: () => cbtApi.exams.list() });
  const exams: any[] = Array.isArray(examData) ? examData : (examData?.items ?? []);
  const [examId, setExamId] = useState("");
  const { data: results, isLoading } = useQuery({
    queryKey: ["cbt-results", examId],
    queryFn: () => cbtApi.results.get(examId),
    enabled: !!examId,
  });
  const attempts: any[] = (results?.attempts ?? []).filter((a: any) => !a.superseded);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">CBT Test Remark</h1>
      <p className="text-slate-500 text-sm mb-6">Add a teacher remark to each student&apos;s test result.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
        <label className="label">Test</label>
        <select value={examId} onChange={(e) => setExamId(e.target.value)} className="input max-w-md">
          <option value="">Select a test…</option>
          {exams.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
        </select>
      </div>

      {!examId ? null : isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : attempts.length === 0 ? (
        <div className="py-16 text-center text-slate-400 text-sm"><MessageSquare size={28} className="mx-auto mb-2 opacity-50" />No results for this test yet.</div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {attempts.map((a) => <RemarkRow key={a.id} attempt={a} examId={examId} canWrite={canWrite} />)}
        </div>
      )}
    </div>
  );
}

function RemarkRow({ attempt, examId, canWrite }: { attempt: any; examId: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const [note, setNote] = useState<string>(attempt.remark_note || "");
  const dirty = note.trim() !== (attempt.remark_note || "").trim();
  const save = useMutation({
    mutationFn: () => cbtApi.attempts.setRemarkNote(attempt.id, note),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-results", examId] }); toast.success("Remark saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save remark."),
  });

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-3">
      <div className="sm:w-56 shrink-0">
        <p className="text-sm font-semibold text-slate-800">{attempt.student_name || attempt.student_id?.slice(0, 8)}</p>
        <p className="text-xs text-slate-400 tabular-nums">{attempt.percentage}% · {attempt.status}</p>
      </div>
      <input value={note} onChange={(e) => setNote(e.target.value)} disabled={!canWrite} className="input flex-1 text-sm" placeholder="Teacher remark on this result…" />
      {canWrite && <button onClick={() => save.mutate()} disabled={!dirty || save.isPending} className="btn-secondary gap-1.5 text-xs py-1.5 shrink-0">{save.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Save</button>}
    </div>
  );
}
