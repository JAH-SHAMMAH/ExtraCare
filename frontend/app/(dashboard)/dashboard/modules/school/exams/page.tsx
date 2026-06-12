"use client";

import { useState } from "react";
import { useExams, useCreateExam } from "@/hooks/useSchool";
import { cn, formatDate } from "@/lib/utils";
import { Award, Plus, X, Loader2, Calendar } from "lucide-react";
import type { Exam } from "@/types";

const STATUS_MAP: Record<string, string> = { scheduled: "bg-blue-50 text-blue-700 border-blue-200", in_progress: "bg-amber-50 text-amber-700 border-amber-200", completed: "bg-emerald-50 text-emerald-700 border-emerald-200", cancelled: "bg-red-50 text-red-700 border-red-200" };

export default function ExamsPage() {
  const [tab, setTab] = useState<"scheduled" | "completed">("scheduled");
  const [showForm, setShowForm] = useState(false);
  const { data, isLoading } = useExams({ status: tab });
  const createExam = useCreateExam();
  const [form, setForm] = useState({ name: "", exam_type: "midterm", subject_id: "", class_id: "", date: "", start_time: "", end_time: "", total_marks: "100", pass_marks: "40" });
  const resetForm = () => { setForm({ name: "", exam_type: "midterm", subject_id: "", class_id: "", date: "", start_time: "", end_time: "", total_marks: "100", pass_marks: "40" }); setShowForm(false); };
  const handleSubmit = () => { createExam.mutate({ ...form, total_marks: parseInt(form.total_marks), pass_marks: parseInt(form.pass_marks) }, { onSuccess: resetForm }); };
  const items = data?.items || (Array.isArray(data) ? data : []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Exams</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Exams & Results</h1>
          <p className="text-slate-500 text-sm mt-0.5">Schedule exams and manage results.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Schedule Exam</button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Schedule New Exam</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Exam Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Type</label><select value={form.exam_type} onChange={(e) => setForm({ ...form, exam_type: e.target.value })} className="input"><option value="midterm">Midterm</option><option value="final">Final</option><option value="quiz">Quiz</option><option value="assignment">Assignment</option><option value="practical">Practical</option></select></div>
            <div><label className="label">Subject ID</label><input value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input" /></div>
            <div><label className="label">Class ID</label><input value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input" /></div>
            <div><label className="label">Date *</label><input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="input" /></div>
            <div><label className="label">Start Time</label><input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="input" /></div>
            <div><label className="label">Total Marks</label><input type="number" value={form.total_marks} onChange={(e) => setForm({ ...form, total_marks: e.target.value })} className="input" /></div>
            <div><label className="label">Pass Marks</label><input type="number" value={form.pass_marks} onChange={(e) => setForm({ ...form, pass_marks: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={resetForm} className="btn-secondary">Cancel</button><button onClick={handleSubmit} disabled={createExam.isPending} className="btn-primary gap-2">{createExam.isPending && <Loader2 size={15} className="animate-spin" />}Schedule</button></div>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        {(["scheduled", "completed"] as const).map((t) => (<button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize", tab === t ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50")}>{t}</button>))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Exam", "Type", "Subject", "Class", "Date", "Marks", "Status"].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => (<tr key={i}><td colSpan={7} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : items.length === 0 ? (<tr><td colSpan={7} className="px-5 py-16 text-center text-slate-400 text-sm"><Award size={32} className="mx-auto mb-2 opacity-50" />No exams found.</td></tr>)
            : items.map((e: Exam) => (
              <tr key={e.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="px-5 py-3.5 text-sm font-bold text-slate-900">{e.name}</td>
                <td className="px-5 py-3.5"><span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{e.exam_type}</span></td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{e.subject_name || "—"}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{e.class_name || "—"}</td>
                <td className="px-5 py-3.5 text-xs text-slate-500">{formatDate(e.date)}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{e.total_marks}</td>
                <td className="px-5 py-3.5"><span className={cn("badge capitalize", STATUS_MAP[e.status] || "")}>{e.status.replace("_", " ")}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
