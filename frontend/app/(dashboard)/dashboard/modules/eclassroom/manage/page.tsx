"use client";

import { useState } from "react";
import { useEcSchedules, useCreateEcSchedule, useUpdateEcSchedule, useDeleteEcSchedule, type EcSchedule } from "@/hooks/useEclassroom";
import { useSessions, useSections } from "@/hooks/usePlatform";
import { useYearGroups } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { CalendarDays, Plus, Loader2, AlertTriangle, Pencil, Trash2, X } from "lucide-react";

const STATUS_STYLE: Record<string, string> = {
  new: "bg-blue-50 text-blue-700 border-blue-200",
  live: "bg-rose-50 text-rose-700 border-rose-200",
  ended: "bg-slate-100 text-slate-500 border-slate-200",
};
const BLANK = { title: "", description: "", section_id: "", session_id: "", year_group_id: "", scheduled_at: "" };
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null);

export default function ManageEclassroomsPage() {
  const [filters, setFilters] = useState({ status: "live_new", year_group_id: "", session_id: "" });
  const { data, isLoading, isError, refetch } = useEcSchedules({
    status: filters.status === "all" ? undefined : filters.status, year_group_id: filters.year_group_id || undefined, session_id: filters.session_id || undefined,
  });
  const { data: sessions } = useSessions();
  const { data: sections } = useSections();
  const { data: yearGroups } = useYearGroups();
  const create = useCreateEcSchedule();
  const update = useUpdateEcSchedule();
  const del = useDeleteEcSchedule();
  const rows = data ?? [];
  const sessionList: any[] = (sessions as any[]) ?? [];
  const sectionList: any[] = (sections as any[]) ?? [];
  const ygList: any[] = (yearGroups as any[]) ?? [];

  const [show, setShow] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [f, setF] = useState({ ...BLANK });
  const reset = () => { setF({ ...BLANK }); setEditing(null); setShow(false); };
  const startEdit = (s: EcSchedule) => { setF({ title: s.title, description: s.description ?? "", section_id: s.section_id ?? "", session_id: s.session_id ?? "", year_group_id: s.year_group_id ?? "", scheduled_at: s.scheduled_at ? s.scheduled_at.slice(0, 16) : "" }); setEditing(s.id); setShow(true); };
  const submit = () => {
    const payload = { title: f.title.trim(), description: f.description || null, section_id: f.section_id || null, session_id: f.session_id || null, year_group_id: f.year_group_id || null, scheduled_at: f.scheduled_at ? new Date(f.scheduled_at).toISOString() : null };
    if (editing) update.mutate({ id: editing, data: payload }, { onSuccess: reset });
    else create.mutate(payload, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>eClassroom</span><span>/</span><span className="text-brand-600 font-semibold">Manage eClassrooms</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage eClassrooms</h1>
          <p className="text-slate-500 text-sm mt-0.5">Scheduled eClassroom sessions by year group.</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Create Schedule</button>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="input max-w-[150px]"><option value="live_new">Live &amp; New</option><option value="live">Live</option><option value="new">New</option><option value="ended">Ended</option><option value="all">All</option></select>
        <select value={filters.year_group_id} onChange={(e) => setFilters({ ...filters, year_group_id: e.target.value })} className="input max-w-[180px]"><option value="">All year groups</option>{ygList.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}</select>
        <select value={filters.session_id} onChange={(e) => setFilters({ ...filters, session_id: e.target.value })} className="input max-w-[180px]"><option value="">All sessions</option>{sessionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit schedule" : "New schedule"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Year 9 Maths — Algebra" /></div>
            <div><label className="label">School</label><select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })} className="input"><option value="">—</option>{sectionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Year group</label><select value={f.year_group_id} onChange={(e) => setF({ ...f, year_group_id: e.target.value })} className="input"><option value="">—</option>{ygList.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}</select></div>
            <div><label className="label">Session</label><select value={f.session_id} onChange={(e) => setF({ ...f, session_id: e.target.value })} className="input"><option value="">—</option>{sessionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Scheduled for</label><input type="datetime-local" value={f.scheduled_at} onChange={(e) => setF({ ...f, scheduled_at: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input min-h-[60px]" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.title.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load schedules.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><CalendarDays size={34} className="mb-3 opacity-40" /><p className="font-semibold">No schedules found</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><p className="text-sm font-semibold text-slate-800 truncate">{s.title}</p><span className={cn("badge capitalize", STATUS_STYLE[s.status] ?? STATUS_STYLE.new)}>{s.status}</span></div>
                <p className="text-xs text-slate-400 truncate">{[s.year_group_name, s.section_name, fmt(s.scheduled_at)].filter(Boolean).join(" · ") || "—"}</p>
              </div>
              {s.status !== "ended" && <><button onClick={() => startEdit(s)} className="text-slate-400 hover:text-brand-600 p-1.5"><Pencil size={14} /></button>
              <button onClick={() => { if (confirm(`Remove “${s.title}”?`)) del.mutate(s.id); }} className="text-slate-400 hover:text-red-600 p-1.5"><Trash2 size={14} /></button></>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
