"use client";

import { useState } from "react";
import { useStudents, useReactivateStudent } from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { getInitials } from "@/lib/utils";
import { Users2, Search, Loader2, AlertTriangle, RotateCcw } from "lucide-react";

const fmt = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null);

/**
 * Shared roster for the withdrawn / inactive student lists (Withdrawal List and
 * Manage Inactive Students). `status="withdrawn"` also shows the reason + date.
 */
export function InactiveRoster({ status, title, subtitle, crumb }: { status: "withdrawn" | "inactive"; title: string; subtitle: string; crumb: string }) {
  const canWrite = useHasPermission("school:write");
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, refetch } = useStudents({ status, search: search || undefined, page_size: 50 });
  const reactivate = useReactivateStudent();
  const rows: any[] = data?.items ?? [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Students</span><span>/</span><span className="text-brand-600 font-semibold">{crumb}</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">{title}</h1>
        <p className="text-slate-500 text-sm mt-0.5">{subtitle}</p>
      </div>

      <div className="relative max-w-sm mb-5"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…" className="input pl-9" /></div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load students.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Users2 size={34} className="mb-3 opacity-40" /><p className="font-semibold">No {status} students</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-5 py-3">
              <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold shrink-0">{getInitials(`${s.first_name} ${s.last_name}`)}</div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{s.first_name} {s.last_name}</p>
                <p className="text-xs text-slate-400 truncate">
                  {s.student_id}
                  {status === "withdrawn" && s.withdrawal_reason ? ` · ${s.withdrawal_reason}` : ""}
                  {status === "withdrawn" && fmt(s.withdrawal_date) ? ` · ${fmt(s.withdrawal_date)}` : ""}
                </p>
              </div>
              {canWrite && <button onClick={() => reactivate.mutate(s.id)} disabled={reactivate.isPending} className="btn-secondary gap-1.5 py-1.5 text-sm text-emerald-700 border-emerald-200 hover:bg-emerald-50"><RotateCcw size={14} /> Reactivate</button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
