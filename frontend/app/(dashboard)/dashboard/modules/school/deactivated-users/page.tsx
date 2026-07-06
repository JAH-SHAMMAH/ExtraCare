"use client";

import { useState } from "react";
import { useUsers, useUpdateUserStatus } from "@/hooks/useUsers";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, getInitials } from "@/lib/utils";
import { UserX, RotateCcw, AlertTriangle, Loader2, UserCheck } from "lucide-react";
import type { UserStatus } from "@/types";

const STATUSES: { value: UserStatus; label: string }[] = [
  { value: "suspended", label: "Suspended" },
  { value: "inactive", label: "Inactive" },
  { value: "locked", label: "Locked" },
];

export default function DeactivatedUsersPage() {
  const canWrite = useHasPermission("users:write");
  const [status, setStatus] = useState<UserStatus>("suspended");
  const { data, isLoading, isError, refetch } = useUsers({ status, page_size: 100 });
  const update = useUpdateUserStatus();

  const items = (data?.items ?? []) as any[];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Admin Management</span><span>/</span><span className="text-brand-600 font-semibold">Manage Deactivated Users</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Deactivated Users</h1>
        <p className="text-slate-500 text-sm mt-0.5">Review suspended, inactive or locked accounts and reactivate them.</p>
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {STATUSES.map((s) => (
          <button key={s.value} onClick={() => setStatus(s.value)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", status === s.value ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{s.label}</button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load users.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><UserCheck size={36} className="mb-3 opacity-40" /><p className="font-semibold">No {status} accounts</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {items.map((u) => (
            <div key={u.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold shrink-0">{getInitials(u.full_name || u.email || "?")}</div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{u.full_name || "—"}</p>
                <p className="text-xs text-slate-400 truncate">{u.email}{u.primary_role ? ` · ${String(u.primary_role).replace(/_/g, " ")}` : ""}</p>
              </div>
              <span className="badge bg-rose-50 text-rose-600 border-rose-200 capitalize">{u.status}</span>
              {canWrite && (
                <button onClick={() => { if (confirm(`Reactivate ${u.full_name || u.email}?`)) update.mutate({ id: u.id, status: "active" }); }} disabled={update.isPending} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2.5 py-1.5 rounded-lg hover:bg-emerald-50">
                  {update.isPending ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />} Reactivate
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><UserX size={12} /> Reactivation requires the users:write capability.</p>}
    </div>
  );
}
