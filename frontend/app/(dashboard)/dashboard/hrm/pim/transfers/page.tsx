"use client";

import { useState } from "react";
import { useTransfers, useCreateTransfer, type Transfer } from "@/hooks/useHrPim";
import { useStaff } from "@/hooks/useUsers";
import { useHrList } from "@/hooks/useHrAdmin";
import { ArrowLeftRight, Loader2, AlertTriangle, ArrowRight, Plus } from "lucide-react";

const fmt = (d?: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null);

export default function TransferLogPage() {
  const { data, isLoading, isError, refetch } = useTransfers();
  const { data: staff } = useStaff();
  const { data: departments } = useHrList("hr_department");
  const create = useCreateTransfer();
  const staffList: any[] = (staff as any[]) ?? [];
  const rows = data ?? [];

  const [f, setF] = useState({ staff_user_id: "", to_department: "", to_unit: "", effective_date: "", reason: "" });
  const reset = () => setF({ staff_user_id: "", to_department: "", to_unit: "", effective_date: "", reason: "" });
  const valid = f.staff_user_id && f.to_department.trim();

  const submit = () => {
    if (!valid) return;
    create.mutate(
      { staff_user_id: f.staff_user_id, to_department: f.to_department.trim(), to_unit: f.to_unit || null, effective_date: f.effective_date || null, reason: f.reason || null },
      { onSuccess: reset },
    );
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span>PIM</span><span>/</span><span className="text-brand-600 font-semibold">Transfer Log</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff Transfer Log</h1>
        <p className="text-slate-500 text-sm mt-0.5">Move a staff member to a new department — the change is applied and logged here.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div><label className="label">Staff *</label>
            <select value={f.staff_user_id} onChange={(e) => setF({ ...f, staff_user_id: e.target.value })} className="input">
              <option value="">Select a staff member…</option>
              {staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}{u.department ? ` — ${u.department}` : ""}</option>)}
            </select>
          </div>
          <div><label className="label">New department *</label>
            <input list="transfer-depts" value={f.to_department} onChange={(e) => setF({ ...f, to_department: e.target.value })} className="input" placeholder="e.g. Administration" />
            <datalist id="transfer-depts">{(departments ?? []).filter((d: any) => d.is_active).map((d: any) => <option key={d.id} value={d.name} />)}</datalist>
          </div>
          <div><label className="label">Unit / team</label><input value={f.to_unit} onChange={(e) => setF({ ...f, to_unit: e.target.value })} className="input" placeholder="Optional" /></div>
          <div><label className="label">Effective date</label><input type="date" value={f.effective_date} onChange={(e) => setF({ ...f, effective_date: e.target.value })} className="input" /></div>
          <div className="md:col-span-2"><label className="label">Reason</label><input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className="input" placeholder="Optional" /></div>
        </div>
        <div className="flex justify-end">
          <button onClick={submit} disabled={!valid || create.isPending} className="btn-primary gap-2">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Log Transfer</button>
        </div>
      </div>

      <h2 className="text-sm font-bold text-slate-800 mb-3">History</h2>
      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load the log.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><ArrowLeftRight size={34} className="mb-3 opacity-40" /><p className="font-semibold">No transfers yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((t: Transfer) => (
            <div key={t.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{t.staff_name || "—"}</p>
                <p className="text-xs text-slate-500 flex items-center gap-1.5 flex-wrap">
                  <span className="text-slate-400">{t.from_department || "—"}</span>
                  <ArrowRight size={11} className="text-slate-300" />
                  <span className="font-medium text-slate-700">{t.to_department}{t.to_unit ? ` · ${t.to_unit}` : ""}</span>
                </p>
                {t.reason && <p className="text-xs text-slate-400 truncate mt-0.5">{t.reason}</p>}
              </div>
              {fmt(t.effective_date) && <span className="text-xs text-slate-400 shrink-0">{fmt(t.effective_date)}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
