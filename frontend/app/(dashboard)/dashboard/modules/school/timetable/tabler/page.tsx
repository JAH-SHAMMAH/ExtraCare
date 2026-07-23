"use client";

import { useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { usePeriodGroups, useTimetableJobs, useCreateTimetableJob, useDeleteTimetableJob, useGenerateTimetable } from "@/hooks/useTimetableModule";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { CalendarClock, Plus, X, Loader2, Trash2, Play } from "lucide-react";
import type { PeriodGroup, TimetableJob } from "@/types";

const fmt = (d?: string) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = { processed: "bg-emerald-50 text-emerald-700 border-emerald-200", failed: "bg-rose-50 text-rose-700 border-rose-200", draft: "bg-slate-50 text-slate-500 border-slate-200" };
  return <span className={cn("badge capitalize", map[status] || map.draft)}>{status}</span>;
}

export default function TimeTablerPage() {
  const canWrite = useHasPermission("school:timetable:write");
  const { data, isLoading } = useTimetableJobs();
  const { data: pgData } = usePeriodGroups();
  const { data: sessions } = useSessions();
  const create = useCreateTimetableJob();
  const del = useDeleteTimetableJob();
  const generate = useGenerateTimetable();

  const jobs: TimetableJob[] = data?.items ?? [];
  const groups: PeriodGroup[] = pgData?.items ?? [];
  const groupName = (id: string | null) => groups.find((g) => g.id === id)?.name || "—";
  const sessionNames = useMemo(() => Array.from(new Set((sessions ?? []).map((s: any) => s.name))), [sessions]);

  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ title: "", period_group_id: "", academic_year: "", period_type: "" });
  const submit = () => create.mutate({ title: form.title.trim(), period_group_id: form.period_group_id || null, academic_year: form.academic_year || null, period_type: form.period_type || null },
    { onSuccess: () => { setShow(false); setForm({ title: "", period_group_id: "", academic_year: "", period_type: "" }); } });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">Time Tabler</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">Time Tabler <span className="text-[10px] font-bold uppercase bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">beta</span></h1>
          <p className="text-slate-500 text-sm mt-0.5">Auto-fill a period group’s lesson slots with subjects (round-robin). Refine in Manage Schedules.</p>
        </div>
        {canWrite && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={15} /> Generate New Timetable</button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Title", "Period Group", "Period Type", "Created", "Last Modified", "Status", "Action"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : jobs.length > 0 ? jobs.map((j, i) => (
              <tr key={j.id} className="hover:bg-slate-50/70">
                <td className="px-4 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-4 py-3 text-sm font-semibold text-slate-800">{j.title}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{groupName(j.period_group_id)}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{j.period_type || "—"}</td>
                <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{fmt(j.created_at)}</td>
                <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{fmt(j.updated_at)}</td>
                <td className="px-4 py-3"><StatusBadge status={j.status} /></td>
                <td className="px-4 py-3">
                  {canWrite && <div className="flex items-center gap-1">
                    <button onClick={() => generate.mutate(j.id)} disabled={generate.isPending} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><Play size={12} /> Generate</button>
                    <button onClick={() => { if (confirm("Delete timetable?")) del.mutate(j.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={14} /></button>
                  </div>}
                </td>
              </tr>
            )) : <tr><td colSpan={8} className="py-16 text-center text-slate-400"><CalendarClock size={30} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">No timetables yet</p></td></tr>}
          </tbody>
        </table>
      </div>

      {show && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setShow(false)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Generate New Timetable</h3><button onClick={() => setShow(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-4">
              <div><label className="label">Title *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" placeholder="e.g. Spring Term Secondary" /></div>
              <div><label className="label">Period Group *</label><select value={form.period_group_id} onChange={(e) => setForm({ ...form, period_group_id: e.target.value, period_type: groups.find((g) => g.id === e.target.value)?.name || "" })} className="input"><option value="">Select…</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
              <div><label className="label">Session</label><select value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input"><option value="">All</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setShow(false)} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.title.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
