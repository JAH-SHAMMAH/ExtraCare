"use client";

import { useState } from "react";
import Link from "next/link";
import { useLeavePolicies, useUpdateLeavePolicy, type LeavePolicy } from "@/hooks/useLeaveConfig";
import { cn } from "@/lib/utils";
import { Settings2, Loader2, AlertTriangle, Check } from "lucide-react";

export default function LeaveConfigurePage() {
  const { data, isLoading, isError, refetch } = useLeavePolicies();
  const rows = data ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/leave" className="hover:text-brand-600">Leave</Link><span>/</span><span className="text-brand-600 font-semibold">Configure</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Leave Configuration</h1>
        <p className="text-slate-500 text-sm mt-0.5">Days granted per year, approval requirement, and which leave types are offered.</p>
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load leave configuration.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((p) => <PolicyRow key={p.leave_type} policy={p} />)}
        </div>
      )}
    </div>
  );
}

function PolicyRow({ policy }: { policy: LeavePolicy }) {
  const update = useUpdateLeavePolicy();
  const [days, setDays] = useState(String(policy.default_days));
  const [approval, setApproval] = useState(policy.requires_approval);
  const [active, setActive] = useState(policy.is_active);

  const dirty = String(policy.default_days) !== days || policy.requires_approval !== approval || policy.is_active !== active;
  const save = () => update.mutate({ leaveType: policy.leave_type, data: { default_days: Number(days) || 0, requires_approval: approval, is_active: active } });

  return (
    <div className={cn("flex flex-wrap items-center gap-3 px-4 py-3", !active && "opacity-60")}>
      <div className="min-w-[130px] flex-1">
        <p className="text-sm font-semibold text-slate-800">{policy.label}</p>
      </div>
      <div className="flex items-center gap-1">
        <input type="number" min={0} value={days} onChange={(e) => setDays(e.target.value)} className="input w-20 py-1.5 text-sm" />
        <span className="text-xs text-slate-400">days/yr</span>
      </div>
      <button onClick={() => setApproval((v) => !v)} className={cn("text-[11px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border", approval ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-400 border-slate-200")} title="Requires approval">
        {approval ? "Approval" : "Auto"}
      </button>
      <button onClick={() => setActive((v) => !v)} className={cn("text-[11px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border", active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-400 border-slate-200")} title="Offered to staff">
        {active ? "Active" : "Off"}
      </button>
      <button onClick={save} disabled={!dirty || update.isPending} className={cn("btn-primary gap-1 py-1.5 text-sm transition-opacity", !dirty && "opacity-0 pointer-events-none")}>
        {update.isPending ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Save
      </button>
    </div>
  );
}
