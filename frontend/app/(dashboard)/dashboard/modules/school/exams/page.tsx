"use client";

import { useEffect, useMemo, useState } from "react";
import { useExams, useCreateExam, useExamResults, useSubmitExamResults } from "@/hooks/useSchool";
import { useSubjects } from "@/hooks/useSchool";
import { useClasses } from "@/hooks/useSchool";
import { cn, formatDate } from "@/lib/utils";
import { Award, Plus, X, Loader2, ClipboardEdit, Users } from "lucide-react";
import { TERMS, DEFAULT_TERM } from "@/lib/terms";
import type { Exam, Subject, SchoolClass } from "@/types";

const STATUS_MAP: Record<string, string> = {
  scheduled: "bg-blue-50 text-blue-700 border-blue-200",
  in_progress: "bg-amber-50 text-amber-700 border-amber-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  cancelled: "bg-red-50 text-red-700 border-red-200",
};

// WAEC default — mirrors the backend GRADING_SCALE for live preview only.
function gradeLetter(score: number | null, total: number): string {
  if (score === null || !total) return "—";
  const pct = (score / total) * 100;
  if (pct >= 70) return "A";
  if (pct >= 60) return "B";
  if (pct >= 50) return "C";
  if (pct >= 45) return "D";
  if (pct >= 40) return "E";
  return "F";
}

export default function ExamsPage() {
  const [tab, setTab] = useState<"scheduled" | "completed">("scheduled");
  const [showForm, setShowForm] = useState(false);
  const [resultsExam, setResultsExam] = useState<Exam | null>(null);

  const { data, isLoading } = useExams({ status: tab });
  const createExam = useCreateExam();
  const { data: subjectsData } = useSubjects();
  const { data: classesData } = useClasses({ page_size: 100 });

  const subjects: Subject[] = subjectsData?.items || [];
  const classes: SchoolClass[] = classesData?.items || [];

  const [form, setForm] = useState({ name: "", exam_type: "midterm", subject_id: "", class_id: "", term: DEFAULT_TERM as string, date: "", start_time: "", end_time: "", total_marks: "100", pass_marks: "40" });
  const resetForm = () => { setForm({ name: "", exam_type: "midterm", subject_id: "", class_id: "", term: DEFAULT_TERM as string, date: "", start_time: "", end_time: "", total_marks: "100", pass_marks: "40" }); setShowForm(false); };
  const handleSubmit = () => {
    createExam.mutate(
      { ...form, subject_id: form.subject_id || undefined, class_id: form.class_id || undefined, total_marks: parseInt(form.total_marks), pass_marks: parseInt(form.pass_marks) },
      { onSuccess: resetForm },
    );
  };
  const items = data?.items || (Array.isArray(data) ? data : []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Exams</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Exams &amp; Results</h1>
          <p className="text-slate-500 text-sm mt-0.5">Schedule exams, then enter marks per class — results feed the report card.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Schedule Exam</button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Schedule New Exam</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Exam Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. First Term Exam" className="input" /></div>
            <div><label className="label">Type</label><select value={form.exam_type} onChange={(e) => setForm({ ...form, exam_type: e.target.value })} className="input"><option value="midterm">Midterm</option><option value="final">Final</option><option value="quiz">Quiz</option><option value="assignment">Assignment</option><option value="practical">Practical</option></select></div>
            <div><label className="label">Subject</label><select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input"><option value="">— Select subject —</option>{subjects.map((s) => (<option key={s.id} value={s.id}>{s.name}{s.code ? ` (${s.code})` : ""}</option>))}</select></div>
            <div><label className="label">Class</label><select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input"><option value="">— Select class —</option>{classes.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}</select></div>
            <div><label className="label">Term</label><select value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input">{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
            <div><label className="label">Date *</label><input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="input" /></div>
            <div><label className="label">Start Time</label><input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="input" /></div>
            <div><label className="label">Total Marks</label><input type="number" value={form.total_marks} onChange={(e) => setForm({ ...form, total_marks: e.target.value })} className="input" /></div>
            <div><label className="label">Pass Marks</label><input type="number" value={form.pass_marks} onChange={(e) => setForm({ ...form, pass_marks: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={resetForm} className="btn-secondary">Cancel</button><button onClick={handleSubmit} disabled={createExam.isPending || !form.name} className="btn-primary gap-2">{createExam.isPending && <Loader2 size={15} className="animate-spin" />}Schedule</button></div>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        {(["scheduled", "completed"] as const).map((t) => (<button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize", tab === t ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50")}>{t}</button>))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Exam", "Type", "Subject", "Class", "Date", "Marks", "Entered", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => (<tr key={i}><td colSpan={9} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : items.length === 0 ? (<tr><td colSpan={9} className="px-5 py-16 text-center text-slate-400 text-sm"><Award size={32} className="mx-auto mb-2 opacity-50" />No exams found.</td></tr>)
            : items.map((e: Exam & { entered_count?: number; total_students?: number }) => (
              <tr key={e.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="px-5 py-3.5 text-sm font-bold text-slate-900 whitespace-nowrap">{e.name}</td>
                <td className="px-5 py-3.5"><span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{e.exam_type}</span></td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{e.subject_name || "—"}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{e.class_name || "—"}</td>
                <td className="px-5 py-3.5 text-xs text-slate-500 whitespace-nowrap">{e.date ? formatDate(e.date) : "—"}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{e.total_marks}</td>
                <td className="px-5 py-3.5 text-xs text-slate-500 tabular-nums">{typeof e.entered_count === "number" ? `${e.entered_count}/${e.total_students ?? 0}` : "—"}</td>
                <td className="px-5 py-3.5"><span className={cn("badge capitalize", STATUS_MAP[e.status] || "")}>{e.status.replace("_", " ")}</span></td>
                <td className="px-5 py-3.5">
                  <button
                    onClick={() => setResultsExam(e)}
                    disabled={!e.class_id || !e.subject_id}
                    title={!e.class_id || !e.subject_id ? "Exam needs a class and subject before entering marks" : "Enter marks"}
                    className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1 disabled:text-slate-300 disabled:no-underline disabled:cursor-not-allowed"
                  >
                    <ClipboardEdit size={13} /> Enter Results
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {resultsExam && <ResultsModal exam={resultsExam} onClose={() => setResultsExam(null)} />}
    </div>
  );
}

// ── Marks-entry modal ────────────────────────────────────────────────────────

interface ResultRow { student_id: string; student_name: string; score: number | null; max_score: number; grade_letter: string | null; }

function ResultsModal({ exam, onClose }: { exam: Exam; onClose: () => void }) {
  const { data, isLoading } = useExamResults(exam.id);
  const submit = useSubmitExamResults();
  const total = exam.total_marks || 100;

  const roster: ResultRow[] = useMemo(() => data?.results || [], [data]);
  // local editable scores keyed by student_id (string so the input can be cleared)
  const [scores, setScores] = useState<Record<string, string>>({});
  useEffect(() => {
    if (roster.length) {
      setScores(Object.fromEntries(roster.map((r) => [r.student_id, r.score === null ? "" : String(r.score)])));
    }
  }, [roster]);

  const handleSave = () => {
    const results = roster.map((r) => {
      const raw = scores[r.student_id];
      return { student_id: r.student_id, score: raw === "" || raw === undefined ? null : Number(raw) };
    });
    submit.mutate({ examId: exam.id, results }, { onSuccess: onClose });
  };

  const entered = Object.values(scores).filter((v) => v !== "" && v !== undefined).length;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl" onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-start justify-between p-5 border-b border-slate-100">
          <div>
            <h2 className="text-base font-bold text-slate-900">{exam.name} — Enter Marks</h2>
            <p className="text-xs text-slate-500 mt-0.5">{exam.subject_name} · {exam.class_name} · out of {total}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-slate-400"><Loader2 size={22} className="animate-spin" /></div>
          ) : roster.length === 0 ? (
            <div className="py-16 text-center text-slate-400 text-sm"><Users size={30} className="mx-auto mb-2 opacity-50" />No students enrolled in this class yet.</div>
          ) : (
            <table className="w-full text-left">
              <thead><tr className="border-b border-slate-100">{["Student", "Score", "Grade"].map((h) => (<th key={h} className="pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {roster.map((r) => {
                  const raw = scores[r.student_id] ?? "";
                  const num = raw === "" ? null : Number(raw);
                  const over = num !== null && num > total;
                  return (
                    <tr key={r.student_id}>
                      <td className="py-2.5 text-sm font-medium text-slate-800">{r.student_name}</td>
                      <td className="py-2.5">
                        <input
                          type="number" min="0" max={total} value={raw}
                          onChange={(ev) => setScores((s) => ({ ...s, [r.student_id]: ev.target.value }))}
                          className={cn("input w-24 text-sm", over && "border-red-400 text-red-600")}
                          placeholder="—"
                        />
                      </td>
                      <td className="py-2.5 text-sm font-bold text-slate-700 tabular-nums">{gradeLetter(num, total)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex items-center justify-between p-5 border-t border-slate-100">
          <span className="text-xs text-slate-500 tabular-nums">{entered}/{roster.length} entered</span>
          <div className="flex gap-3">
            <button onClick={onClose} className="btn-secondary">Cancel</button>
            <button onClick={handleSave} disabled={submit.isPending || roster.length === 0} className="btn-primary gap-2">{submit.isPending && <Loader2 size={15} className="animate-spin" />}Save Results</button>
          </div>
        </div>
      </div>
    </div>
  );
}
