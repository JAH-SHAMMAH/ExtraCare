"use client";

import { useState } from "react";
import Link from "next/link";
import { useStudentDailyReports, useSaveStudentDailyReport, useDeleteStudentDailyReport } from "@/hooks/useFeedbackExtras";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, Smile } from "lucide-react";
import type { StudentDailyReport } from "@/types";

const MOODS = ["", "happy", "neutral", "sad", "excited", "tired"];
const BLANK = { student_id: "", report_date: new Date().toISOString().substring(0, 10), mood: "", academic: "", behaviour: "", notes: "" };

export default function StudentDailyReportsPage() {
  const canWrite = useHasPermission("school:write");
  const [filterStudent, setFilterStudent] = useState<string | null>(null);
  const { data, isLoading } = useStudentDailyReports(filterStudent ? { student_id: filterStudent } : undefined);
  const save = useSaveStudentDailyReport();
  const remove = useDeleteStudentDailyReport();
  const reports: StudentDailyReport[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (r: StudentDailyReport) => {
    setForm({ student_id: r.student_id, report_date: r.report_date, mood: r.mood || "", academic: r.academic || "", behaviour: r.behaviour || "", notes: r.notes || "" });
    setEditing(r.id); setShow(true);
  };
  const submit = () => {
    const payload: Record<string, unknown> = { report_date: form.report_date, mood: form.mood || null, academic: form.academic || null, behaviour: form.behaviour || null, notes: form.notes || null };
    if (!editing) payload.student_id = form.student_id;
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">Student Daily Report</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Student Daily Report</h1>
          <p className="text-slate-500 text-sm mt-0.5">Per-student daily notes — mood, academic and behaviour observations.</p>
        </div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> New report</button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4">
        <label className="label">Filter by student</label>
        <EntityPicker type="student" value={filterStudent} onChange={setFilterStudent} />
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit report" : "New report"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            {!editing && <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>}
            <div><label className="label">Date</label><input type="date" value={form.report_date} onChange={(e) => setForm({ ...form, report_date: e.target.value })} className="input" /></div>
            <div><label className="label">Mood</label><select value={form.mood} onChange={(e) => setForm({ ...form, mood: e.target.value })} className="input capitalize">{MOODS.map((m) => <option key={m} value={m}>{m || "—"}</option>)}</select></div>
            <div className="md:col-span-2"><label className="label">Academic</label><textarea value={form.academic} onChange={(e) => setForm({ ...form, academic: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-2"><label className="label">Behaviour</label><textarea value={form.behaviour} onChange={(e) => setForm({ ...form, behaviour: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={(!editing && !form.student_id) || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : reports.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400 text-sm"><Smile size={30} className="mx-auto mb-2 opacity-50" />No student daily reports yet.</div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-slate-900">{r.student_name || r.student_id.slice(0, 8)}</p>
                  <p className="text-xs text-slate-400">{formatDate(r.report_date)}{r.mood ? <span className="capitalize"> · {r.mood}</span> : null}</p>
                </div>
                {canWrite && (
                  <div className="flex items-center gap-2">
                    <button onClick={() => startEdit(r)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                    <button onClick={() => { if (confirm("Delete this report?")) remove.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
              {r.academic && <p className="text-xs text-slate-500 mt-2"><span className="font-semibold text-slate-700">Academic:</span> {r.academic}</p>}
              {r.behaviour && <p className="text-xs text-slate-500 mt-1"><span className="font-semibold text-slate-700">Behaviour:</span> {r.behaviour}</p>}
              {r.notes && <p className="text-xs text-slate-500 mt-1"><span className="font-semibold text-slate-700">Notes:</span> {r.notes}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
