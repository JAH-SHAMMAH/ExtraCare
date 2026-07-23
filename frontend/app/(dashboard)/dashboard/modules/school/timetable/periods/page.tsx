"use client";

import { useEffect, useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { usePeriodGroups, usePeriods, useDeletePeriod, useGeneratePeriods } from "@/hooks/useTimetableModule";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Clock, Plus, X, Loader2, Trash2, AlertTriangle, Layers } from "lucide-react";
import type { PeriodGroup, Period } from "@/types";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
type Break = { name: string; after_period: number; minutes: number };

export default function ManagePeriodsPage() {
  const canWrite = useHasPermission("school:timetable:write");
  const { data: pgData } = usePeriodGroups();
  const { data: sessions } = useSessions();
  const sessionNames = useMemo(() => Array.from(new Set((sessions ?? []).map((s: any) => s.name))), [sessions]);
  const [session, setSession] = useState("");
  const [groupId, setGroupId] = useState("");
  const groups: PeriodGroup[] = pgData?.items ?? [];

  useEffect(() => { if (!session && sessionNames.length) setSession(sessionNames[0]); }, [sessionNames, session]);
  useEffect(() => { if (!groupId && groups.length) setGroupId(groups[0].id); }, [groups, groupId]);

  const { data, isLoading, isError, refetch } = usePeriods({ period_group_id: groupId || null, academic_year: session || undefined });
  const del = useDeletePeriod();
  const periods: Period[] = data?.items ?? [];
  const [showGen, setShowGen] = useState(false);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">Manage Periods</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Periods</h1>
        <p className="text-slate-500 text-sm mt-0.5">Define each period group’s day/time rows. Create period groups in TimeTable Setup.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Period groups */}
        <div className="lg:col-span-1">
          <p className="text-xs font-black uppercase tracking-widest text-slate-400 mb-2 flex items-center gap-1.5"><Layers size={13} /> Period Groups</p>
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50 overflow-hidden">
            {groups.length === 0 ? <p className="px-4 py-6 text-sm text-slate-400 text-center">No groups. Add them in Setup.</p>
            : groups.map((g) => (
              <button key={g.id} onClick={() => setGroupId(g.id)} className={cn("w-full text-left px-4 py-3 text-sm font-semibold transition-colors", groupId === g.id ? "bg-brand-600 text-white" : "text-slate-700 hover:bg-slate-50")}>{g.name}</button>
            ))}
          </div>
        </div>

        {/* Periods */}
        <div className="lg:col-span-3">
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <select value={session} onChange={(e) => setSession(e.target.value)} className="input max-w-[180px]"><option value="">All sessions</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select>
            {canWrite && groupId && <button onClick={() => setShowGen(true)} className="btn-primary gap-2"><Plus size={15} /> Generate New Period</button>}
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Day", "Period Starts", "Period Ends", "Period Type", "Action"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
                : isError ? <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={26} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary mt-2">Retry</button></td></tr>
                : periods.length > 0 ? periods.map((p, i) => (
                  <tr key={p.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-2.5 text-sm text-slate-500">{i + 1}</td>
                    <td className="px-4 py-2.5 text-sm text-slate-700">{DAYS[p.day_of_week]}</td>
                    <td className="px-4 py-2.5 text-sm text-slate-700">{p.start_time}</td>
                    <td className="px-4 py-2.5 text-sm text-slate-700">{p.end_time}</td>
                    <td className="px-4 py-2.5"><span className={cn("badge", p.period_type === "LESSON" ? "bg-slate-50 text-slate-600 border-slate-200" : "bg-amber-50 text-amber-700 border-amber-200")}>{p.period_type}</span></td>
                    <td className="px-4 py-2.5">{canWrite && <button onClick={() => { if (confirm("Delete period?")) del.mutate(p.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={14} /></button>}</td>
                  </tr>
                )) : <tr><td colSpan={6} className="py-16 text-center text-slate-400"><Clock size={30} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">No periods yet</p>{canWrite && groupId && <p className="text-xs mt-1">Use “Generate New Period”.</p>}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {showGen && groupId && <GenerateModal groupId={groupId} session={session} onClose={() => setShowGen(false)} />}
    </div>
  );
}

function GenerateModal({ groupId, session, onClose }: { groupId: string; session: string; onClose: () => void }) {
  const gen = useGeneratePeriods();
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [f, setF] = useState({ periods_per_day: "8", start_time: "08:00", minutes_per_period: "40" });
  const [breaks, setBreaks] = useState<Break[]>([]);

  const toggleDay = (d: number) => setDays((s) => (s.includes(d) ? s.filter((x) => x !== d) : [...s, d]).sort());
  const submit = () => gen.mutate({
    period_group_id: groupId, academic_year: session || null, days,
    periods_per_day: Number(f.periods_per_day), start_time: f.start_time, minutes_per_period: Number(f.minutes_per_period),
    non_lesson: breaks.filter((b) => b.name.trim()).map((b) => ({ name: b.name.trim(), after_period: b.after_period, minutes: b.minutes })),
    replace_existing: true,
  }, { onSuccess: onClose });

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Generate Periods</h3><button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
        <div className="px-6 py-4 space-y-4 max-h-[65vh] overflow-y-auto">
          <div>
            <label className="label">Days *</label>
            <div className="flex flex-wrap gap-2">{DAYS.map((d, i) => <button key={d} type="button" onClick={() => toggleDay(i)} className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold border", days.includes(i) ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-500 border-slate-200")}>{d.slice(0, 3)}</button>)}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Total Periods Per Day *</label><input type="number" value={f.periods_per_day} onChange={(e) => setF({ ...f, periods_per_day: e.target.value })} className="input" /></div>
            <div><label className="label">Period Starts *</label><input type="time" value={f.start_time} onChange={(e) => setF({ ...f, start_time: e.target.value })} className="input" /></div>
            <div><label className="label">Minutes Per Lecture Period *</label><input type="number" value={f.minutes_per_period} onChange={(e) => setF({ ...f, minutes_per_period: e.target.value })} className="input" /></div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-2"><label className="label mb-0">Non-lesson periods</label><button onClick={() => setBreaks([...breaks, { name: "", after_period: 1, minutes: 15 }])} className="text-xs font-semibold text-brand-600 hover:text-brand-700 inline-flex items-center gap-1"><Plus size={12} /> Add</button></div>
            {breaks.length === 0 ? <p className="text-xs text-slate-400">Optional — e.g. Short Break after period 2.</p> : (
              <div className="space-y-2">
                {breaks.map((b, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input value={b.name} onChange={(e) => setBreaks(breaks.map((x, i) => i === idx ? { ...x, name: e.target.value } : x))} className="input flex-1" placeholder="e.g. SHORT BREAK" />
                    <input type="number" value={b.after_period} onChange={(e) => setBreaks(breaks.map((x, i) => i === idx ? { ...x, after_period: Number(e.target.value) } : x))} className="input w-24" title="After period #" />
                    <input type="number" value={b.minutes} onChange={(e) => setBreaks(breaks.map((x, i) => i === idx ? { ...x, minutes: Number(e.target.value) } : x))} className="input w-20" title="Minutes" />
                    <button onClick={() => setBreaks(breaks.filter((_, i) => i !== idx))} className="text-rose-400 hover:text-rose-600 p-1"><Trash2 size={14} /></button>
                  </div>
                ))}
                <p className="text-[11px] text-slate-400">Columns: name · after period # · minutes</p>
              </div>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={onClose} className="btn-secondary">Close</button><button onClick={submit} disabled={days.length === 0 || gen.isPending} className="btn-primary gap-2">{gen.isPending && <Loader2 size={15} className="animate-spin" />}Generate</button></div>
      </div>
    </div>
  );
}
