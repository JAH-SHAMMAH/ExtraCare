"use client";

import { useState } from "react";
import { useCalendar, useCreateEvent, useDeleteEvent } from "@/hooks/useOperations";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { Calendar, Plus, X, Loader2, Trash2, AlertTriangle, MapPin } from "lucide-react";

const CATEGORIES = ["academic", "holiday", "exam", "meeting", "sports", "other"];
const CAT_STYLE: Record<string, string> = {
  academic: "bg-blue-50 text-blue-700 border-blue-200",
  holiday: "bg-emerald-50 text-emerald-700 border-emerald-200",
  exam: "bg-rose-50 text-rose-700 border-rose-200",
  meeting: "bg-indigo-50 text-indigo-700 border-indigo-200",
  sports: "bg-amber-50 text-amber-700 border-amber-200",
  other: "bg-slate-50 text-slate-600 border-slate-200",
};

export default function CalendarPage() {
  const canWrite = useHasPermission("school:write");
  const { data, isLoading, isError, refetch } = useCalendar();
  const create = useCreateEvent();
  const del = useDeleteEvent();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ title: "", start_at: "", end_at: "", category: "academic", location: "", description: "", all_day: false });

  const reset = () => { setForm({ title: "", start_at: "", end_at: "", category: "academic", location: "", description: "", all_day: false }); setShow(false); };
  const submit = () => create.mutate({
    title: form.title.trim(), start_at: form.start_at, end_at: form.end_at || null,
    category: form.category, location: form.location || null, description: form.description || null, all_day: form.all_day,
  }, { onSuccess: reset });

  const rows = data?.items;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Operations</span><span>/</span><span className="text-brand-600 font-semibold">Calendar &amp; Planner</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Calendar &amp; Planner</h1>
          <p className="text-slate-500 text-sm mt-0.5">School-wide events, holidays and key dates.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Event</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Event</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2"><label className="label">Title *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" /></div>
            <div><label className="label">Start *</label><input type="datetime-local" value={form.start_at} onChange={(e) => setForm({ ...form, start_at: e.target.value })} className="input" /></div>
            <div><label className="label">End</label><input type="datetime-local" value={form.end_at} onChange={(e) => setForm({ ...form, end_at: e.target.value })} className="input" /></div>
            <div><label className="label">Category</label><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input capitalize">{CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
            <div><label className="label">Location</label><input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="input" /></div>
            <div className="md:col-span-2 flex items-center gap-2"><input id="allday" type="checkbox" checked={form.all_day} onChange={(e) => setForm({ ...form, all_day: e.target.checked })} /><label htmlFor="allday" className="text-xs font-medium text-slate-700">All day</label></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.title.trim() || !form.start_at || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load the calendar.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows && rows.length > 0 ? (
        <div className="space-y-2">
          {rows.map((e) => (
            <div key={e.id} className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-4">
              <div className="text-center shrink-0 w-14">
                <p className="text-[10px] uppercase font-bold text-slate-400">{new Date(e.start_at).toLocaleDateString(undefined, { month: "short" })}</p>
                <p className="text-xl font-black text-slate-800">{new Date(e.start_at).getDate()}</p>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-900 truncate">{e.title}</h3>
                  {e.category && <span className={cn("badge capitalize", CAT_STYLE[e.category] || "")}>{e.category}</span>}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {e.all_day ? "All day" : new Date(e.start_at).toLocaleString()}
                  {e.location && <span className="inline-flex items-center gap-1 ml-2"><MapPin size={11} /> {e.location}</span>}
                </p>
              </div>
              {canWrite && <button onClick={() => { if (confirm("Delete this event?")) del.mutate(e.id); }} className="text-slate-400 hover:text-red-600 p-1 shrink-0"><Trash2 size={14} /></button>}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Calendar size={36} className="mb-3 opacity-40" /><p className="font-semibold">No events yet</p></div>
      )}
    </div>
  );
}
