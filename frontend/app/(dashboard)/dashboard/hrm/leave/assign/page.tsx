"use client";

import { useState } from "react";
import Link from "next/link";
import { useStaff } from "@/hooks/useUsers";
import { useLeavePolicies, useAssignLeave } from "@/hooks/useLeaveConfig";
import { Loader2, CalendarPlus, Info } from "lucide-react";

export default function AssignLeavePage() {
  const { data: staff } = useStaff();
  const { data: policies } = useLeavePolicies();
  const assign = useAssignLeave();
  const staffList: any[] = (staff as any[]) ?? [];
  const types = (policies ?? []).filter((p) => p.is_active);

  const [f, setF] = useState({ user_id: "", leave_type: "annual", start_date: "", end_date: "", reason: "" });
  const reset = () => setF({ user_id: "", leave_type: "annual", start_date: "", end_date: "", reason: "" });

  const valid = f.user_id && f.start_date && f.end_date && f.end_date >= f.start_date;
  const submit = () => {
    if (!valid) return;
    assign.mutate(
      { user_id: f.user_id, leave_type: f.leave_type, start_date: f.start_date, end_date: f.end_date, reason: f.reason || null },
      { onSuccess: reset },
    );
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/leave" className="hover:text-brand-600">Leave</Link><span>/</span><span className="text-brand-600 font-semibold">Assign Leave</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Assign Leave</h1>
        <p className="text-slate-500 text-sm mt-0.5">Book leave for a staff member directly — recorded as approved on their behalf.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="label">Staff *</label>
            <select value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} className="input">
              <option value="">Select a staff member…</option>
              {staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Leave type</label>
            <select value={f.leave_type} onChange={(e) => setF({ ...f, leave_type: e.target.value })} className="input">
              {types.map((t) => <option key={t.leave_type} value={t.leave_type}>{t.label}</option>)}
            </select>
          </div>
          <div />
          <div><label className="label">Start date *</label><input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className="input" /></div>
          <div><label className="label">End date *</label><input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className="input" /></div>
          <div className="md:col-span-2"><label className="label">Reason</label><input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className="input" placeholder="Optional" /></div>
        </div>

        {f.start_date && f.end_date && f.end_date < f.start_date && (
          <p className="text-xs text-rose-600 mt-3">End date must be on or after the start date.</p>
        )}

        <div className="flex items-center justify-between mt-5">
          <p className="text-xs text-slate-400 flex items-center gap-1"><Info size={12} /> Counts against the staff member’s entitlement.</p>
          <button onClick={submit} disabled={!valid || assign.isPending} className="btn-primary gap-2">
            {assign.isPending ? <Loader2 size={15} className="animate-spin" /> : <CalendarPlus size={15} />} Assign Leave
          </button>
        </div>
      </div>
    </div>
  );
}
