"use client";

import { useMemo, useState } from "react";
import { useWeeks, useCreateWeek, useGenerateWeeks, useUpdateWeek, useDeleteWeek } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { TERMS } from "@/lib/terms";
import { cn, formatDate } from "@/lib/utils";
import {
  CalendarClock, Plus, X, Loader2, Lock, Unlock, Trash2, Sparkles, Sun, Pencil, AlertTriangle,
} from "lucide-react";
import type { AcademicWeek } from "@/types";

function defaultAcademicYear(): string {
  const now = new Date();
  const start = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1; // Aug rollover
  return `${start}/${start + 1}`;
}

export default function WeekEntriesPage() {
  const canWrite = useHasPermission("settings:write");
  const [year, setYear] = useState(defaultAcademicYear());
  const [term, setTerm] = useState<string>(TERMS[0]);
  const [showAdd, setShowAdd] = useState(false);
  const [showGen, setShowGen] = useState(false);
  const [editing, setEditing] = useState<AcademicWeek | null>(null);

  const { data, isLoading } = useWeeks({ academic_year: year || undefined, term: term || undefined });
  const weeks: AcademicWeek[] = data || [];
  const del = useDeleteWeek();
  const update = useUpdateWeek();

  const scoped = year.trim() && term;
  const nextWeekNumber = useMemo(() => (weeks.length ? Math.max(...weeks.map((w) => w.week_number)) + 1 : 1), [weeks]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Admin Management</span><span>/</span><span className="text-brand-600 font-semibold">Manage Week Entries</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Week Entries</h1>
        <p className="text-slate-500 text-sm mt-0.5">Define the academic weeks within each term — the calendar backbone for attendance, remarks and reports.</p>
      </div>

      {/* Scope */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap items-end gap-3">
        <div><label className="label">Academic year</label><input value={year} onChange={(e) => setYear(e.target.value)} placeholder="2025/2026" className="input w-40" /></div>
        <div><label className="label">Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input w-36">{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
        {canWrite && scoped && (
          <div className="flex gap-2 ml-auto">
            {weeks.length === 0 && <button onClick={() => setShowGen(true)} className="btn-secondary gap-2"><Sparkles size={15} />Auto-generate</button>}
            <button onClick={() => setShowAdd(true)} className="btn-primary gap-2"><Plus size={15} />Add week</button>
          </div>
        )}
      </div>

      {!scoped ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <CalendarClock size={34} className="mx-auto mb-3 opacity-40" /><p className="font-semibold text-slate-500">Pick an academic year and term</p>
        </div>
      ) : isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : weeks.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <CalendarClock size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No weeks for {term} {year}</p>
          <p className="text-sm mt-1">Auto-generate from the term dates, or add weeks one by one.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Week", "Dates", "Label", ""].map((h) => (<th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {weeks.map((w) => (
                <tr key={w.id} className={cn("hover:bg-slate-50/70", w.is_holiday && "bg-amber-50/30")}>
                  <td className="px-5 py-3 text-sm font-bold text-slate-900 whitespace-nowrap">
                    Week {w.week_number}
                    {w.is_locked && <Lock size={11} className="inline ml-1.5 -mt-0.5 text-slate-400" />}
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-600 whitespace-nowrap">{formatDate(w.start_date)} – {formatDate(w.end_date)}</td>
                  <td className="px-5 py-3 text-sm text-slate-500">
                    {w.label || <span className="text-slate-300">—</span>}
                    {w.is_holiday && <span className="badge bg-amber-50 text-amber-700 border-amber-200 ml-2 inline-flex items-center gap-1"><Sun size={10} />holiday</span>}
                  </td>
                  <td className="px-5 py-3">
                    {canWrite && (
                      <div className="flex items-center gap-2.5 justify-end">
                        <button onClick={() => update.mutate({ id: w.id, data: { is_locked: !w.is_locked } })} title={w.is_locked ? "Unlock" : "Lock"} className="text-slate-400 hover:text-slate-700">
                          {w.is_locked ? <Unlock size={14} /> : <Lock size={14} />}
                        </button>
                        <button onClick={() => setEditing(w)} disabled={w.is_locked} title="Edit" className="text-slate-400 hover:text-brand-600 disabled:opacity-30 disabled:hover:text-slate-400"><Pencil size={14} /></button>
                        <button onClick={() => { if (confirm(`Delete Week ${w.week_number}?`)) del.mutate(w.id); }} disabled={w.is_locked} title="Delete" className="text-slate-400 hover:text-rose-600 disabled:opacity-30 disabled:hover:text-slate-400"><Trash2 size={14} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><AlertTriangle size={12} /> Editing the week calendar requires the settings:write capability.</p>}

      {showAdd && <WeekModal year={year} term={term} weekNumber={nextWeekNumber} onClose={() => setShowAdd(false)} />}
      {editing && <WeekModal year={year} term={term} existing={editing} onClose={() => setEditing(null)} />}
      {showGen && <GenerateModal year={year} term={term} onClose={() => setShowGen(false)} />}
    </div>
  );
}

function WeekModal({ year, term, weekNumber, existing, onClose }: { year: string; term: string; weekNumber?: number; existing?: AcademicWeek; onClose: () => void }) {
  const create = useCreateWeek();
  const update = useUpdateWeek();
  const [form, setForm] = useState({
    week_number: existing?.week_number ?? weekNumber ?? 1,
    start_date: existing?.start_date ?? "",
    end_date: existing?.end_date ?? "",
    label: existing?.label ?? "",
    is_holiday: existing?.is_holiday ?? false,
  });
  const pending = create.isPending || update.isPending;

  const submit = () => {
    if (!form.start_date || !form.end_date) return;
    const payload = { ...form, label: form.label.trim() || null, week_number: Number(form.week_number) };
    if (existing) {
      update.mutate({ id: existing.id, data: payload }, { onSuccess: onClose });
    } else {
      create.mutate({ ...payload, academic_year: year, term }, { onSuccess: onClose });
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h2 className="text-base font-bold text-slate-900">{existing ? `Edit Week ${existing.week_number}` : "Add week"} <span className="font-normal text-slate-400 text-sm">· {term} {year}</span></h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Week number</label><input type="number" min={1} max={60} value={form.week_number} onChange={(e) => setForm({ ...form, week_number: Number(e.target.value) })} className="input" /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Start date</label><input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input" /></div>
            <div><label className="label">End date</label><input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="input" /></div>
          </div>
          <div><label className="label">Label (optional)</label><input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} placeholder="e.g. Mid-term break" className="input" /></div>
          <label className="flex items-center gap-2.5 cursor-pointer"><input type="checkbox" checked={form.is_holiday} onChange={(e) => setForm({ ...form, is_holiday: e.target.checked })} className="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" /><span className="text-sm text-slate-700">Non-teaching / holiday week</span></label>
        </div>
        <div className="flex justify-end gap-3 p-5 border-t border-slate-100">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={submit} disabled={pending || !form.start_date || !form.end_date} className="btn-primary gap-2">{pending && <Loader2 size={15} className="animate-spin" />}{existing ? "Save" : "Add"}</button>
        </div>
      </div>
    </div>
  );
}

function GenerateModal({ year, term, onClose }: { year: string; term: string; onClose: () => void }) {
  const generate = useGenerateWeeks();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const submit = () => {
    if (!start || !end) return;
    generate.mutate({ academic_year: year, term, start_date: start, end_date: end }, { onSuccess: onClose });
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h2 className="text-base font-bold text-slate-900 inline-flex items-center gap-2"><Sparkles size={17} className="text-brand-600" />Auto-generate weeks</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-slate-500">Fills sequential 7-day weeks across the term for <span className="font-semibold text-slate-700">{term} {year}</span>. You can edit or delete individual weeks afterwards.</p>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Term starts</label><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="input" /></div>
            <div><label className="label">Term ends</label><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="input" /></div>
          </div>
        </div>
        <div className="flex justify-end gap-3 p-5 border-t border-slate-100">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={submit} disabled={generate.isPending || !start || !end} className="btn-primary gap-2">{generate.isPending && <Loader2 size={15} className="animate-spin" />}Generate</button>
        </div>
      </div>
    </div>
  );
}
