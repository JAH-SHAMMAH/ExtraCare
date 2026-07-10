"use client";

import { useState } from "react";
import Link from "next/link";
import { useDailyReports, useSaveDailyReport, useDeleteDailyReport } from "@/hooks/useFeedbackExtras";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, CalendarDays } from "lucide-react";
import type { DailyReport } from "@/types";

const BLANK = { report_date: new Date().toISOString().substring(0, 10), summary: "", highlights: "", challenges: "" };

export default function DailyReportsPage() {
  const canWrite = useHasPermission("school:write");
  const [mine, setMine] = useState(true);
  const { data, isLoading } = useDailyReports({ mine });
  const save = useSaveDailyReport();
  const remove = useDeleteDailyReport();
  const reports: DailyReport[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (r: DailyReport) => {
    setForm({ report_date: r.report_date, summary: r.summary, highlights: r.highlights || "", challenges: r.challenges || "" });
    setEditing(r.id); setShow(true);
  };
  const submit = () => {
    const payload = { report_date: form.report_date, summary: form.summary, highlights: form.highlights || null, challenges: form.challenges || null };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">Daily Report</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Daily Report</h1>
          <p className="text-slate-500 text-sm mt-0.5">Log your daily activity — highlights, challenges and a summary.</p>
        </div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> New report</button>}
      </div>

      <div className="flex bg-slate-100 rounded-lg p-0.5 w-fit mb-4">
        <button onClick={() => setMine(true)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}>Mine</button>
        <button onClick={() => setMine(false)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}>All staff</button>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit report" : "New report"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Date</label><input type="date" value={form.report_date} onChange={(e) => setForm({ ...form, report_date: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Summary</label><textarea value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} className="input" rows={3} /></div>
            <div><label className="label">Highlights</label><textarea value={form.highlights} onChange={(e) => setForm({ ...form, highlights: e.target.value })} className="input" rows={2} /></div>
            <div><label className="label">Challenges</label><textarea value={form.challenges} onChange={(e) => setForm({ ...form, challenges: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.summary || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : reports.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400 text-sm"><CalendarDays size={30} className="mx-auto mb-2 opacity-50" />No daily reports yet.</div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-slate-900">{formatDate(r.report_date)}</p>
                  <p className="text-xs text-slate-400">{r.author_name || "—"}</p>
                </div>
                {canWrite && (
                  <div className="flex items-center gap-2">
                    <button onClick={() => startEdit(r)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                    <button onClick={() => { if (confirm("Delete this report?")) remove.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
              <p className="text-sm text-slate-700 whitespace-pre-wrap mt-2">{r.summary}</p>
              {r.highlights && <p className="text-xs text-slate-500 mt-2"><span className="font-semibold text-emerald-600">Highlights:</span> {r.highlights}</p>}
              {r.challenges && <p className="text-xs text-slate-500 mt-1"><span className="font-semibold text-amber-600">Challenges:</span> {r.challenges}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
