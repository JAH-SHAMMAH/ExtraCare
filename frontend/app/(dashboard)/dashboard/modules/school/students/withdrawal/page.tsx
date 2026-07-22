"use client";

import { useState } from "react";
import { useStudents, useWithdrawStudent } from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, getInitials } from "@/lib/utils";
import { UserMinus, Search, Loader2, AlertTriangle, X, Lock } from "lucide-react";

export default function ManageWithdrawalPage() {
  const canWrite = useHasPermission("school:write");
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, refetch } = useStudents({ status: "active", search: search || undefined, page_size: 50 });
  const withdraw = useWithdrawStudent();
  const rows: any[] = data?.items ?? [];

  const [target, setTarget] = useState<any | null>(null);
  const [f, setF] = useState({ reason: "", effective_date: "" });
  const close = () => { setTarget(null); setF({ reason: "", effective_date: "" }); };
  const submit = () => {
    if (!target) return;
    withdraw.mutate({ id: target.id, data: { reason: f.reason || null, effective_date: f.effective_date || null } }, { onSuccess: close });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Manage Withdrawal</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Withdrawal</h1>
        <p className="text-slate-500 text-sm mt-0.5">Withdraw an active student — records the reason and date and marks them inactive.</p>
      </div>

      <div className="relative max-w-sm mb-5"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search active students…" className="input pl-9" /></div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load students.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><UserMinus size={34} className="mb-3 opacity-40" /><p className="font-semibold">No active students</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-5 py-3">
              <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold shrink-0">{getInitials(`${s.first_name} ${s.last_name}`)}</div>
              <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-800 truncate">{s.first_name} {s.last_name}</p><p className="text-xs text-slate-400">{s.student_id}</p></div>
              {canWrite && <button onClick={() => setTarget(s)} className="btn-secondary gap-1.5 py-1.5 text-sm text-rose-600 border-rose-200 hover:bg-rose-50"><UserMinus size={14} /> Withdraw</button>}
            </div>
          ))}
        </div>
      )}
      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Withdrawing requires write access.</p>}

      {target && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={close}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Withdraw {target.first_name} {target.last_name}</h3><button onClick={close} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-4">
              <div><label className="label">Reason</label><textarea value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className="input min-h-[70px]" placeholder="e.g. Relocated / Transferred to another school" /></div>
              <div><label className="label">Effective date</label><input type="date" value={f.effective_date} onChange={(e) => setF({ ...f, effective_date: e.target.value })} className="input" /><p className="text-xs text-slate-400 mt-1">Defaults to today if left blank.</p></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={close} className="btn-secondary">Cancel</button><button onClick={submit} disabled={withdraw.isPending} className="btn-primary gap-2 bg-rose-600 hover:bg-rose-700">{withdraw.isPending && <Loader2 size={15} className="animate-spin" />}Withdraw</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
