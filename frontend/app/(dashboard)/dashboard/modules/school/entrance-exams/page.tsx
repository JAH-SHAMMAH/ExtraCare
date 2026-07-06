"use client";

import { useState } from "react";
import {
  useEntranceExams, useCreateEntranceExam, useUpdateEntranceExam, useDeleteEntranceExam,
  useExamResults, useAddExamResult, useUpdateExamResult, useDeleteExamResult,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  Award, Plus, X, Loader2, Edit2, Trash2, AlertTriangle, ArrowLeft, ClipboardList,
} from "lucide-react";
import type { EntranceExam } from "@/types";

const OUTCOME_STYLE: Record<string, string> = {
  pending: "bg-slate-50 text-slate-500 border-slate-200",
  pass: "bg-emerald-50 text-emerald-700 border-emerald-200",
  fail: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function EntranceExamsPage() {
  const canWrite = useHasPermission("school:admissions:write");
  const [openExam, setOpenExam] = useState<EntranceExam | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<EntranceExam | null>(null);
  const [form, setForm] = useState({ title: "", exam_date: "", subject: "", max_score: "100", status: "scheduled", notes: "" });

  const { data, isLoading, isError, refetch } = useEntranceExams();
  const createExam = useCreateEntranceExam();
  const updateExam = useUpdateEntranceExam();
  const deleteExam = useDeleteEntranceExam();

  const reset = () => { setForm({ title: "", exam_date: "", subject: "", max_score: "100", status: "scheduled", notes: "" }); setEditing(null); setShowForm(false); };
  const openEdit = (e: EntranceExam) => {
    setForm({ title: e.title, exam_date: e.exam_date ?? "", subject: e.subject ?? "", max_score: String(e.max_score), status: e.status, notes: e.notes ?? "" });
    setEditing(e); setShowForm(true);
  };
  const submit = () => {
    const payload = {
      title: form.title.trim(), exam_date: form.exam_date || null, subject: form.subject || null,
      max_score: Number(form.max_score) || 100, status: form.status, notes: form.notes || null,
    };
    if (editing) updateExam.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    else createExam.mutate(payload, { onSuccess: reset });
  };

  if (openExam) return <ExamResultsView exam={openExam} canWrite={canWrite} onBack={() => setOpenExam(null)} />;

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Entrance Exams</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Entrance Exams</h1>
          <p className="text-slate-500 text-sm mt-0.5">Schedule entrance assessments and record candidate scores.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Exam</button>}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Exam" : "New Exam"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="label">Title *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" placeholder="e.g. 2026 Entrance Assessment" /></div>
            <div><label className="label">Exam Date</label><input type="date" value={form.exam_date} onChange={(e) => setForm({ ...form, exam_date: e.target.value })} className="input" /></div>
            <div><label className="label">Subject</label><input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="input" placeholder="e.g. General Paper" /></div>
            <div><label className="label">Max Score</label><input type="number" value={form.max_score} onChange={(e) => setForm({ ...form, max_score: e.target.value })} className="input" /></div>
            <div><label className="label">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
                <option value="scheduled">Scheduled</option><option value="completed">Completed</option>
              </select>
            </div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.title.trim() || createExam.isPending || updateExam.isPending} className="btn-primary gap-2">
              {(createExam.isPending || updateExam.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />)}
        </div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load entrance exams.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : rows && rows.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((e) => (
            <div key={e.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-bold text-slate-900">{e.title}</h3>
                <span className={cn("badge capitalize", e.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-blue-50 text-blue-700 border-blue-200")}>{e.status}</span>
              </div>
              <div className="text-xs text-slate-500 space-y-1 mb-4">
                {e.subject && <p>Subject: {e.subject}</p>}
                {e.exam_date && <p>Date: {formatDate(e.exam_date)}</p>}
                <p>Max score: {e.max_score}</p>
                <p>{e.result_count} result{e.result_count === 1 ? "" : "s"} recorded</p>
              </div>
              <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                <button onClick={() => setOpenExam(e)} className="text-xs font-semibold text-brand-600 hover:text-brand-700">Results →</button>
                {canWrite && (
                  <div className="flex items-center gap-1">
                    <button onClick={() => openEdit(e)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                    <button onClick={() => { if (confirm("Delete this exam and its results?")) deleteExam.mutate(e.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <Award size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No entrance exams yet</p>
        </div>
      )}
    </div>
  );
}

function ExamResultsView({ exam, canWrite, onBack }: { exam: EntranceExam; canWrite: boolean; onBack: () => void }) {
  const { data: results, isLoading, isError, refetch } = useExamResults(exam.id);
  const addResult = useAddExamResult();
  const updateResult = useUpdateExamResult();
  const deleteResult = useDeleteExamResult();
  const [form, setForm] = useState({ candidate_name: "", score: "", outcome: "pending", remark: "" });

  const add = () => {
    addResult.mutate(
      { examId: exam.id, data: { candidate_name: form.candidate_name.trim(), score: form.score ? Number(form.score) : null, outcome: form.outcome, remark: form.remark || null } },
      { onSuccess: () => setForm({ candidate_name: "", score: "", outcome: "pending", remark: "" }) },
    );
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to exams</button>
      <h1 className="text-2xl font-black text-slate-900">{exam.title}</h1>
      <p className="text-sm text-slate-500 mt-1 mb-6">{exam.subject ? `${exam.subject} · ` : ""}Max score {exam.max_score}</p>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div className="md:col-span-2"><label className="label">Candidate *</label><input value={form.candidate_name} onChange={(e) => setForm({ ...form, candidate_name: e.target.value })} className="input" /></div>
          <div><label className="label">Score</label><input type="number" value={form.score} onChange={(e) => setForm({ ...form, score: e.target.value })} className="input" /></div>
          <div><label className="label">Outcome</label>
            <select value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })} className="input capitalize">
              <option value="pending">Pending</option><option value="pass">Pass</option><option value="fail">Fail</option>
            </select>
          </div>
          <button onClick={add} disabled={!form.candidate_name.trim() || addResult.isPending} className="btn-primary gap-2 justify-center">
            {addResult.isPending && <Loader2 size={14} className="animate-spin" />} Add
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Candidate", "Score", "Outcome", "Remark", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-12 text-center">
                <AlertTriangle size={24} className="mx-auto mb-2 text-amber-400" />
                <p className="text-sm text-slate-600">Couldn’t load results.</p>
                <button onClick={() => refetch()} className="mt-2 btn-secondary">Retry</button>
              </td></tr>
            ) : results && results.length > 0 ? (
              results.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{r.candidate_name}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{r.score ?? "—"}{r.score != null ? ` / ${exam.max_score}` : ""}</td>
                  <td className="px-5 py-4">
                    {canWrite ? (
                      <select value={r.outcome} onChange={(e) => updateResult.mutate({ resultId: r.id, data: { outcome: e.target.value } })} className={cn("input py-1 text-xs capitalize w-28 border", OUTCOME_STYLE[r.outcome] || "")}>
                        <option value="pending">Pending</option><option value="pass">Pass</option><option value="fail">Fail</option>
                      </select>
                    ) : <span className={cn("badge capitalize", OUTCOME_STYLE[r.outcome] || "")}>{r.outcome}</span>}
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500">{r.remark || "—"}</td>
                  <td className="px-5 py-4">
                    {canWrite && <button onClick={() => { if (confirm("Remove this result?")) deleteResult.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-12 text-center text-slate-400">
                <ClipboardList size={28} className="mx-auto mb-2 opacity-40" />
                <p className="text-sm">No results recorded yet.</p>
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
