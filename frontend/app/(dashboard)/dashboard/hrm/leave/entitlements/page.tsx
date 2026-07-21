"use client";

import { useEntitlements, type Entitlement } from "@/hooks/useLeaveConfig";
import { cn } from "@/lib/utils";
import { CalendarClock, AlertTriangle } from "lucide-react";

export default function EntitlementsPage() {
  const { data, isLoading, isError, refetch } = useEntitlements();
  const rows = data ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">My Entitlements</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Leave Entitlements</h1>
        <p className="text-slate-500 text-sm mt-0.5">Your leave balance for {new Date().getFullYear()} — allocated, used and remaining.</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load your entitlements.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <CalendarClock size={34} className="mb-3 opacity-40" /><p className="font-semibold">No leave types configured</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {rows.map((e) => <Card key={e.leave_type} row={e} />)}
        </div>
      )}
    </div>
  );
}

function Card({ row }: { row: Entitlement }) {
  const pct = row.allocated > 0 ? Math.min(100, Math.round((row.used / row.allocated) * 100)) : 0;
  const low = row.remaining <= 0 && row.allocated > 0;
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-bold text-slate-800">{row.label}</p>
        <span className={cn("text-sm font-black", low ? "text-rose-600" : "text-slate-900")}>{row.remaining}<span className="text-xs font-semibold text-slate-400"> left</span></span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden mb-2">
        <div className={cn("h-full rounded-full", low ? "bg-rose-400" : "bg-brand-500")} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-slate-400">{row.used} used of {row.allocated} day{row.allocated === 1 ? "" : "s"}</p>
    </div>
  );
}
