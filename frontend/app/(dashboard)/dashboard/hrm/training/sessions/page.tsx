"use client";

import Link from "next/link";
import { useAllSessions, type TrainingSession } from "@/hooks/useHrTraining";
import { CalendarDays, AlertTriangle, ArrowLeft, MapPin, UserRound } from "lucide-react";

const fmt = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) : "Unscheduled");

export default function AllSessionsPage() {
  const { data, isLoading, isError, refetch } = useAllSessions();
  const rows = data ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <button onClick={() => history.back()} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to training</button>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/training" className="hover:text-brand-600">Training</Link><span>/</span><span className="text-brand-600 font-semibold">Sessions</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Training Sessions</h1>
        <p className="text-slate-500 text-sm mt-0.5">All scheduled sessions across every training program.</p>
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load sessions.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><CalendarDays size={34} className="mb-3 opacity-40" /><p className="font-semibold">No sessions scheduled</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((s: TrainingSession) => (
            <div key={s.id} className="flex items-center gap-4 px-5 py-3.5">
              <div className="text-center shrink-0 w-16">
                <p className="text-xs font-bold text-brand-600">{fmt(s.session_date)}</p>
                {s.start_time && <p className="text-[11px] text-slate-400">{s.start_time.slice(0, 5)}</p>}
              </div>
              <div className="min-w-0 flex-1 border-l border-slate-100 pl-4">
                <p className="text-sm font-semibold text-slate-800 truncate">{s.training_title}{s.title ? ` — ${s.title}` : ""}</p>
                <p className="text-xs text-slate-400 flex items-center gap-2 flex-wrap">
                  {s.facilitator && <span className="inline-flex items-center gap-1"><UserRound size={11} /> {s.facilitator}</span>}
                  {s.location && <span className="inline-flex items-center gap-1"><MapPin size={11} /> {s.location}</span>}
                  {!s.facilitator && !s.location && "—"}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
