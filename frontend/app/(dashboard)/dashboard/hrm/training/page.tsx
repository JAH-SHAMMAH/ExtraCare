"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useTrainings, useCreateTraining, useUpdateTraining, useDeleteTraining,
  useTrainingSessions, useAddSession, useDeleteSession, type Training,
} from "@/hooks/useHrTraining";
import { cn } from "@/lib/utils";
import { GraduationCap, Plus, Loader2, Trash2, AlertTriangle, ArrowLeft, CalendarDays, X } from "lucide-react";

const STATUS = ["planned", "ongoing", "completed"];
const STATUS_STYLE: Record<string, string> = {
  planned: "bg-slate-50 text-slate-600 border-slate-200",
  ongoing: "bg-blue-50 text-blue-700 border-blue-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

export default function TrainingPage() {
  const [open, setOpen] = useState<Training | null>(null);
  if (open) return <TrainingDetail training={open} onBack={() => setOpen(null)} />;
  return <TrainingsList onOpen={setOpen} />;
}

function TrainingsList({ onOpen }: { onOpen: (t: Training) => void }) {
  const { data, isLoading, isError, refetch } = useTrainings();
  const create = useCreateTraining();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ title: "", category: "", status: "planned", description: "" });
  const reset = () => { setF({ title: "", category: "", status: "planned", description: "" }); setShow(false); };
  const rows = data ?? [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Training</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Training</h1>
          <p className="text-slate-500 text-sm mt-0.5">Training programs and their scheduled sessions.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/hrm/training/sessions" className="btn-secondary gap-2"><CalendarDays size={15} /> All Sessions</Link>
          <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Training</button>
        </div>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Safeguarding" /></div>
            <div><label className="label">Category</label><input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="input" placeholder="Optional" /></div>
            <div><label className="label">Status</label><select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="input capitalize">{STATUS.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input min-h-[70px]" /></div>
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={() => create.mutate({ title: f.title.trim(), category: f.category || null, status: f.status, description: f.description || null }, { onSuccess: reset })} disabled={!f.title.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load trainings.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><GraduationCap size={36} className="mb-3 opacity-40" /><p className="font-semibold">No trainings yet</p></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rows.map((t) => (
            <button key={t.id} onClick={() => onOpen(t)} className="text-left bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-bold text-slate-900">{t.title}</h3>
                <span className={cn("badge capitalize", STATUS_STYLE[t.status] ?? STATUS_STYLE.planned)}>{t.status}</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">{t.category || "—"}</p>
              <span className="inline-flex items-center gap-1 text-sm font-semibold text-slate-700"><CalendarDays size={13} /> {t.session_count} session{t.session_count === 1 ? "" : "s"}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function TrainingDetail({ training, onBack }: { training: Training; onBack: () => void }) {
  const { data: sessions, isLoading } = useTrainingSessions(training.id);
  const addSession = useAddSession();
  const delSession = useDeleteSession();
  const update = useUpdateTraining();
  const del = useDeleteTraining();
  const [s, setS] = useState({ title: "", session_date: "", start_time: "", location: "", facilitator: "" });
  const resetS = () => setS({ title: "", session_date: "", start_time: "", location: "", facilitator: "" });

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to trainings</button>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900">{training.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{training.category || "Uncategorised"}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={training.status} onChange={(e) => update.mutate({ id: training.id, data: { status: e.target.value } })} className={cn("input py-1.5 text-sm capitalize", STATUS_STYLE[training.status])}>
            {STATUS.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
          <button onClick={() => { if (confirm("Delete this training and its sessions?")) { del.mutate(training.id); onBack(); } }} className="text-slate-400 hover:text-red-600 p-2"><Trash2 size={15} /></button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap gap-2 items-end">
        <div className="flex-1 min-w-[130px]"><label className="label">Session</label><input value={s.title} onChange={(e) => setS({ ...s, title: e.target.value })} className="input" placeholder="Label (optional)" /></div>
        <div className="min-w-[140px]"><label className="label">Date</label><input type="date" value={s.session_date} onChange={(e) => setS({ ...s, session_date: e.target.value })} className="input" /></div>
        <div className="min-w-[110px]"><label className="label">Time</label><input type="time" value={s.start_time} onChange={(e) => setS({ ...s, start_time: e.target.value })} className="input" /></div>
        <div className="flex-1 min-w-[120px]"><label className="label">Facilitator</label><input value={s.facilitator} onChange={(e) => setS({ ...s, facilitator: e.target.value })} className="input" /></div>
        <button onClick={() => addSession.mutate({ trainingId: training.id, data: { training_id: training.id, title: s.title || null, session_date: s.session_date || null, start_time: s.start_time || null, facilitator: s.facilitator || null } }, { onSuccess: resetS })} disabled={addSession.isPending} className="btn-primary justify-center">{addSession.isPending ? <Loader2 size={14} className="animate-spin" /> : "Add"}</button>
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : (sessions ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-12 text-slate-400"><CalendarDays size={30} className="mb-2 opacity-40" /><p className="font-semibold">No sessions yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {sessions!.map((ss) => (
            <div key={ss.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{ss.title || "Session"}</p>
                <p className="text-xs text-slate-400 truncate">{[ss.session_date, ss.start_time?.slice(0, 5), ss.facilitator, ss.location].filter(Boolean).join(" · ") || "—"}</p>
              </div>
              <button onClick={() => delSession.mutate(ss.id)} className="text-slate-400 hover:text-red-600 p-1"><X size={15} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
