"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useCBTExams, useExamResults, useAttemptReview, useRemarkAttempt, useResetAttempt, useCreateIntervention } from "@/hooks/useSchoolExperience";
import { cbtApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { BarChart3, Download, Loader2, ArrowLeft, ClipboardEdit, X, AlertTriangle, CheckCircle2, Flag, RotateCcw } from "lucide-react";
import { toast } from "sonner";

const STATUS_STYLE: Record<string, string> = {
  graded: "bg-emerald-50 text-emerald-700 border-emerald-200",
  submitted: "bg-blue-50 text-blue-700 border-blue-200",
  in_progress: "bg-amber-50 text-amber-700 border-amber-200",
};

interface AttemptRow {
  id: string; student_id: string; student_name: string | null; score: number; max_score: number;
  percentage: number; status: string; submitted_at: string | null; needs_review: boolean;
}

export default function CBTResultsPage() {
  const [examId, setExamId] = useState("");
  const [gradingId, setGradingId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const { data: examsData } = useCBTExams({ page_size: 100 });
  const exams: any[] = examsData?.items || [];
  const { data, isLoading } = useExamResults(examId || null);
  const resetAttempt = useResetAttempt();
  const createIntervention = useCreateIntervention();
  const canWrite = useHasPermission("school:write");

  useEffect(() => { if (!examId && exams.length) setExamId(exams[0].id); }, [exams, examId]);

  const attempts: AttemptRow[] = data?.attempts || [];
  const stats = data?.stats;

  const doExport = async () => {
    if (!examId) return;
    setExporting(true);
    try {
      const blob = await cbtApi.results.exportCsv(examId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cbt-results-${(data?.exam?.title || "exam").replace(/\s+/g, "_")}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Export failed.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>CBT</span><span>/</span><span className="text-brand-600 font-semibold">Result Manager</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Result Manager</h1>
          <p className="text-slate-500 text-sm mt-0.5">Scores per student, subjective grading, and CSV export.</p>
        </div>
        <button onClick={doExport} disabled={!examId || exporting || attempts.length === 0} className="btn-secondary gap-2">
          {exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Export CSV
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
        <label className="label">Exam</label>
        <select value={examId} onChange={(e) => setExamId(e.target.value)} className="input">
          <option value="">— Select an exam —</option>
          {exams.map((e) => (<option key={e.id} value={e.id}>{e.title}</option>))}
        </select>
      </div>

      {!examId ? null : isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : (
        <>
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
              {[
                { label: "Attempts", value: stats.attempts },
                { label: "Average", value: stats.average },
                { label: "Highest", value: stats.highest },
                { label: "Pass rate", value: `${stats.pass_rate}%` },
                { label: "Need review", value: stats.pending_review, warn: stats.pending_review > 0 },
              ].map((s) => (
                <div key={s.label} className={cn("bg-white rounded-xl border p-4", s.warn ? "border-amber-200" : "border-slate-200")}>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{s.label}</p>
                  <p className={cn("text-xl font-black tabular-nums", s.warn ? "text-amber-700" : "text-slate-900")}>{s.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Attempts */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Score", "%", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {attempts.length === 0 ? (
                  <tr><td colSpan={5} className="px-5 py-16 text-center text-slate-400 text-sm"><BarChart3 size={30} className="mx-auto mb-2 opacity-50" />No attempts for this exam yet.</td></tr>
                ) : attempts.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3 text-sm font-bold text-slate-900 whitespace-nowrap">{a.student_name || a.student_id}</td>
                    <td className="px-5 py-3 text-sm text-slate-700 tabular-nums">{a.score} / {a.max_score}</td>
                    <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{a.percentage}%</td>
                    <td className="px-5 py-3">
                      <span className={cn("badge capitalize", STATUS_STYLE[a.status] || "bg-slate-50 text-slate-600 border-slate-200")}>{a.status.replace("_", " ")}</span>
                      {a.needs_review && <span className="badge bg-amber-50 text-amber-700 border-amber-200 ml-1 inline-flex items-center gap-1"><AlertTriangle size={10} />review</span>}
                    </td>
                    <td className="px-5 py-3">
                      {canWrite ? (
                      <div className="flex items-center gap-3">
                        <button onClick={() => setGradingId(a.id)} className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1"><ClipboardEdit size={13} />Grade</button>
                        <button
                          onClick={() => createIntervention.mutate({ student_id: a.student_id, exam_id: examId, attempt_id: a.id, reason: `Scored ${a.percentage}% on ${data?.exam?.title ?? "this exam"}` })}
                          disabled={createIntervention.isPending}
                          className="text-xs text-amber-600 font-semibold hover:underline inline-flex items-center gap-1" title="Flag for intervention"
                        ><Flag size={13} />Flag</button>
                        <button
                          onClick={() => { if (confirm(`Reset ${a.student_name || "this student"}'s attempt? Their answers are cleared and they can retake.`)) resetAttempt.mutate(a.id); }}
                          disabled={resetAttempt.isPending}
                          className="text-xs text-slate-500 font-semibold hover:underline inline-flex items-center gap-1" title="Reset for a retake"
                        ><RotateCcw size={13} />Reset</button>
                      </div>
                      ) : <span className="text-xs text-slate-300">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {gradingId && <GradeModal attemptId={gradingId} onClose={() => setGradingId(null)} />}
    </div>
  );
}

interface ReviewAnswer {
  answer_id: string; question_text: string | null; question_type: string; max_points: number;
  correct_answer: string | null; answer_text: string | null; is_correct: boolean | null;
  points_awarded: number | null; needs_grading: boolean;
}

function GradeModal({ attemptId, onClose }: { attemptId: string; onClose: () => void }) {
  const { data, isLoading } = useAttemptReview(attemptId);
  const remark = useRemarkAttempt();
  const answers: ReviewAnswer[] = data?.answers || [];

  const [pts, setPts] = useState<Record<string, string>>({});
  useEffect(() => {
    if (answers.length) setPts(Object.fromEntries(answers.map((a) => [a.answer_id, a.points_awarded == null ? "" : String(a.points_awarded)])));
  }, [answers]);

  const save = () => {
    const items = answers
      .map((a) => ({ answer_id: a.answer_id, raw: pts[a.answer_id] }))
      .filter((x) => x.raw !== "" && x.raw !== undefined)
      .map((x) => ({ answer_id: x.answer_id, points_awarded: Number(x.raw) }));
    remark.mutate({ attempt_id: attemptId, items }, { onSuccess: onClose });
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[88vh] flex flex-col shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between p-5 border-b border-slate-100">
          <div>
            <h2 className="text-base font-bold text-slate-900">Grade attempt</h2>
            <p className="text-xs text-slate-500 mt-0.5">{data?.attempt?.student_name || ""} · award points for each answer</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {isLoading ? (
            <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          ) : answers.map((a, i) => (
            <div key={a.answer_id} className={cn("rounded-xl border p-4", a.needs_grading ? "border-amber-200 bg-amber-50/40" : "border-slate-200")}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <p className="text-sm font-semibold text-slate-800">{i + 1}. {a.question_text || "—"}</p>
                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 shrink-0 capitalize">{a.question_type.replace("_", " ")}</span>
              </div>
              <p className="text-xs text-slate-500 mb-1"><span className="font-semibold text-slate-600">Answer:</span> {a.answer_text || <span className="italic text-slate-400">(blank)</span>}</p>
              {a.correct_answer && a.question_type !== "long_answer" && a.question_type !== "short_answer" && (
                <p className="text-xs text-emerald-600 mb-2 inline-flex items-center gap-1"><CheckCircle2 size={12} /> Correct: {a.correct_answer}</p>
              )}
              <div className="flex items-center gap-2 mt-2">
                <label className="text-xs text-slate-500">Points</label>
                <input
                  type="number" min="0" max={a.max_points} step="0.5"
                  value={pts[a.answer_id] ?? ""}
                  onChange={(e) => setPts((s) => ({ ...s, [a.answer_id]: e.target.value }))}
                  className="input w-24 text-sm"
                  placeholder={a.needs_grading ? "grade" : "—"}
                />
                <span className="text-xs text-slate-400">/ {a.max_points}</span>
                {a.needs_grading && <span className="text-[11px] text-amber-600 inline-flex items-center gap-1"><AlertTriangle size={11} />needs grading</span>}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-3 p-5 border-t border-slate-100">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={save} disabled={remark.isPending} className="btn-primary gap-2">{remark.isPending && <Loader2 size={15} className="animate-spin" />}Save marks</button>
        </div>
      </div>
    </div>
  );
}
