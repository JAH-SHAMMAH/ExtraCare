"use client";

import { useState } from "react";
import {
  useTranscripts, useCreateTranscript, useUpdateTranscript, useDeleteTranscript,
  useAddTranscriptEntry, useDeleteTranscriptEntry,
} from "@/hooks/useAcademics";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { PrintLetterhead } from "@/components/branding/Brand";
import { cn } from "@/lib/utils";
import {
  FileText, Plus, X, Loader2, Trash2, AlertTriangle, ArrowLeft, CheckCircle2, Printer,
} from "lucide-react";
import type { Transcript } from "@/types";

type EntryDraft = { subject_name: string; score: string; grade: string };

export default function MarkBooksPage() {
  const canWrite = useHasPermission("school:grades:write");
  const [openId, setOpenId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ student_id: "", academic_year: "", term: "", remark: "" });
  const [entries, setEntries] = useState<EntryDraft[]>([{ subject_name: "", score: "", grade: "" }]);

  const { data, isLoading, isError, refetch } = useTranscripts();
  const create = useCreateTranscript();

  const reset = () => { setForm({ student_id: "", academic_year: "", term: "", remark: "" }); setEntries([{ subject_name: "", score: "", grade: "" }]); setShowForm(false); };
  const submit = () => {
    const cleaned = entries.filter((e) => e.subject_name.trim()).map((e) => ({ subject_name: e.subject_name.trim(), score: e.score ? Number(e.score) : null, grade: e.grade || null }));
    create.mutate(
      { student_id: form.student_id, academic_year: form.academic_year || null, term: form.term || null, remark: form.remark || null, entries: cleaned },
      { onSuccess: reset },
    );
  };

  if (openId) return <TranscriptDetail id={openId} canWrite={canWrite} onBack={() => setOpenId(null)} />;

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Academics</span><span>/</span><span className="text-brand-600 font-semibold">Mark Books &amp; Transcripts</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Mark Books &amp; Transcripts</h1>
          <p className="text-slate-500 text-sm mt-0.5">Consolidated academic records per student and term.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Transcript</button>}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Transcript</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" placeholder="2025/2026" /></div>
            <div><label className="label">Term</label><input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input" placeholder="Term 1" /></div>
          </div>
          <label className="label">Subjects</label>
          <div className="space-y-2 mb-3">
            {entries.map((e, i) => (
              <div key={i} className="grid grid-cols-12 gap-2">
                <input value={e.subject_name} onChange={(ev) => setEntries(entries.map((x, j) => j === i ? { ...x, subject_name: ev.target.value } : x))} className="input col-span-6" placeholder="Subject" />
                <input type="number" value={e.score} onChange={(ev) => setEntries(entries.map((x, j) => j === i ? { ...x, score: ev.target.value } : x))} className="input col-span-3" placeholder="Score" />
                <input value={e.grade} onChange={(ev) => setEntries(entries.map((x, j) => j === i ? { ...x, grade: ev.target.value } : x))} className="input col-span-2" placeholder="Grade" />
                <button onClick={() => setEntries(entries.filter((_, j) => j !== i))} className="col-span-1 text-slate-400 hover:text-red-600"><X size={15} /></button>
              </div>
            ))}
          </div>
          <button onClick={() => setEntries([...entries, { subject_name: "", score: "", grade: "" }])} className="text-xs font-semibold text-brand-600 hover:text-brand-700 mb-4">+ Add subject</button>
          <div><label className="label">Remark</label><textarea value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} className="input" rows={2} /></div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.student_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-32 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load transcripts.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows && rows.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((t) => (
            <button key={t.id} onClick={() => setOpenId(t.id)} className="text-left bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-bold text-slate-900">{t.student_name || t.student_id.slice(0, 8)}</h3>
                <span className={cn("badge capitalize", t.status === "issued" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{t.status}</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">{[t.academic_year, t.term].filter(Boolean).join(" · ") || "—"}</p>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">{t.entries.length} subject{t.entries.length === 1 ? "" : "s"}</span>
                <span className="font-bold text-slate-800">Avg {t.average ?? "—"}</span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><FileText size={36} className="mb-3 opacity-40" /><p className="font-semibold">No transcripts yet</p></div>
      )}
    </div>
  );
}

function TranscriptDetail({ id, canWrite, onBack }: { id: string; canWrite: boolean; onBack: () => void }) {
  const { data, isLoading } = useTranscripts();
  const t = (data?.items ?? []).find((x: Transcript) => x.id === id);
  const update = useUpdateTranscript();
  const del = useDeleteTranscript();
  const addEntry = useAddTranscriptEntry();
  const delEntry = useDeleteTranscriptEntry();
  const [entry, setEntry] = useState({ subject_name: "", score: "", grade: "" });

  if (isLoading || !t) {
    return <div className="p-8 max-w-3xl mx-auto"><button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 mb-4"><ArrowLeft size={14} /> Back</button><div className="h-40 bg-slate-100 rounded-xl animate-pulse" /></div>;
  }

  const add = () => addEntry.mutate(
    { id, data: { subject_name: entry.subject_name.trim(), score: entry.score ? Number(entry.score) : null, grade: entry.grade || null } },
    { onSuccess: () => setEntry({ subject_name: "", score: "", grade: "" }) },
  );

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4 no-print"><ArrowLeft size={14} /> Back to transcripts</button>
      <PrintLetterhead title="Transcript" subtitle={[t.academic_year, t.term].filter(Boolean).join(" — ") || undefined} />
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900">{t.student_name || t.student_id.slice(0, 8)}</h1>
          <p className="text-sm text-slate-500 mt-1">{[t.academic_year, t.term].filter(Boolean).join(" · ") || "—"} · Average <span className="font-bold text-slate-700">{t.average ?? "—"}</span></p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => window.print()} title="Print / save as PDF" className="inline-flex items-center gap-1 btn-secondary no-print"><Printer size={14} /> Print</button>
          {canWrite && (
            <div className="flex items-center gap-2 no-print">
              {t.status !== "issued" && <button onClick={() => update.mutate({ id, data: { status: "issued" } })} className="inline-flex items-center gap-1 btn-secondary text-emerald-700"><CheckCircle2 size={14} /> Issue</button>}
              <button onClick={() => { if (confirm("Delete this transcript?")) { del.mutate(id); onBack(); } }} className="text-slate-400 hover:text-red-600 p-2"><Trash2 size={15} /></button>
            </div>
          )}
        </div>
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 grid grid-cols-12 gap-2 items-end no-print">
          <div className="col-span-6"><label className="label">Subject</label><input value={entry.subject_name} onChange={(e) => setEntry({ ...entry, subject_name: e.target.value })} className="input" /></div>
          <div className="col-span-2"><label className="label">Score</label><input type="number" value={entry.score} onChange={(e) => setEntry({ ...entry, score: e.target.value })} className="input" /></div>
          <div className="col-span-2"><label className="label">Grade</label><input value={entry.grade} onChange={(e) => setEntry({ ...entry, grade: e.target.value })} className="input" /></div>
          <button onClick={add} disabled={!entry.subject_name.trim() || addEntry.isPending} className="col-span-2 btn-primary justify-center">{addEntry.isPending ? <Loader2 size={14} className="animate-spin" /> : "Add"}</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Subject", "Score", "Grade", ""].map((h) => <th key={h} className={cn("px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500", h === "" && "print:hidden")}>{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {t.entries.length > 0 ? t.entries.map((e) => (
              <tr key={e.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-700">{e.subject_name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{e.score ?? "—"}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{e.grade || "—"}</td>
                <td className="px-5 py-3 print:hidden">{canWrite && <button onClick={() => delEntry.mutate({ id, entryId: e.id })} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>}</td>
              </tr>
            )) : <tr><td colSpan={4} className="py-10 text-center text-slate-400 text-sm">No subjects on this transcript yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
