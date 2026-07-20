"use client";

import { useMyCases } from "@/hooks/useHrExtended";
import { cn } from "@/lib/utils";
import { ShieldCheck, AlertTriangle, CheckCircle2 } from "lucide-react";

const SEVERITY: Record<string, string> = {
  minor: "bg-amber-50 text-amber-700 border-amber-200",
  major: "bg-orange-50 text-orange-700 border-orange-200",
  gross: "bg-rose-50 text-rose-700 border-rose-200",
};
const STATUS: Record<string, string> = {
  open: "bg-blue-50 text-blue-700 border-blue-200",
  under_review: "bg-violet-50 text-violet-700 border-violet-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dismissed: "bg-slate-100 text-slate-500 border-slate-200",
};
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null);

export default function MyActionsPage() {
  const { data, isLoading, isError, refetch } = useMyCases();
  const rows = data ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">My Actions</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Actions</h1>
        <p className="text-slate-500 text-sm mt-0.5">Disciplinary records raised in relation to you, and the action taken.</p>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load your record.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-center">
          <ShieldCheck size={40} className="mb-3 text-emerald-400" />
          <p className="font-bold text-slate-700">Clean record</p>
          <p className="text-sm text-slate-400 mt-1">You have no disciplinary actions on file.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((c: any) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3 mb-2">
                <h3 className="text-sm font-bold text-slate-900">{c.title}</h3>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={cn("badge capitalize", SEVERITY[c.severity] ?? SEVERITY.minor)}>{c.severity}</span>
                  <span className={cn("badge capitalize", STATUS[c.status] ?? STATUS.open)}>{String(c.status).replace("_", " ")}</span>
                </div>
              </div>
              {c.description && <p className="text-sm text-slate-600 mb-3">{c.description}</p>}
              {c.action_taken && (
                <div className="flex items-start gap-2 text-sm bg-slate-50 rounded-lg px-3 py-2 mb-2">
                  <CheckCircle2 size={15} className="text-emerald-500 mt-0.5 shrink-0" />
                  <span className="text-slate-700"><span className="font-semibold">Action taken:</span> {c.action_taken}</span>
                </div>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                {fmt(c.incident_on) && <span>Incident: {fmt(c.incident_on)}</span>}
                {fmt(c.resolved_on) && <span>Resolved: {fmt(c.resolved_on)}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
