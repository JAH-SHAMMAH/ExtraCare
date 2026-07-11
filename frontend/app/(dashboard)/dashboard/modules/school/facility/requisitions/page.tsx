"use client";

import { useState } from "react";
import Link from "next/link";
import { cn, formatDate } from "@/lib/utils";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { useFacilityRequisitions, useCreateRequisition, useApproveRequisition, useDisburseRequisition, useFacilityMaintenance } from "@/hooks/useFacility";
import { ArrowLeft, Plus, X, Loader2, Receipt, CheckCircle2, Banknote } from "lucide-react";
import type { FacilityRequisition } from "@/types";

const STATUS_STYLE: Record<string, string> = { draft: "bg-slate-50 text-slate-500 border-slate-200", pending: "bg-amber-50 text-amber-700 border-amber-200", approved: "bg-blue-50 text-blue-700 border-blue-200", rejected: "bg-rose-50 text-rose-700 border-rose-200", disbursed: "bg-emerald-50 text-emerald-700 border-emerald-200" };

export default function FacilityRequisitionsPage() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const [mine, setMine] = useState(true);
  const { data, isLoading } = useFacilityRequisitions(mine);
  const { data: maintenance } = useFacilityMaintenance(false);
  const create = useCreateRequisition();
  const approve = useApproveRequisition();
  const disburse = useDisburseRequisition();
  const rows: FacilityRequisition[] = data || [];
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ title: "", maintenance_id: "", maintenance_type: "", maintenance_cost: "0", requisition_cost: "0" });
  const reset = () => { setForm({ title: "", maintenance_id: "", maintenance_type: "", maintenance_cost: "0", requisition_cost: "0" }); setShow(false); };
  const submit = () => create.mutate({ title: form.title, maintenance_id: form.maintenance_id || null, maintenance_type: form.maintenance_type || null, maintenance_cost: Number(form.maintenance_cost) || 0, requisition_cost: Number(form.requisition_cost) || 0 }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="flex items-end justify-between mb-4 gap-4">
        <div><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Requisitions</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Requisitions</h1><p className="text-slate-500 text-sm mt-0.5">Routed to the approval level its cost meets. Disbursement records the payout (ledger posting is a follow-up).</p></div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Raise Requisition</button>}
      </div>
      <div className="flex bg-slate-100 rounded-lg p-0.5 w-fit mb-4"><button onClick={() => setMine(true)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}>My Requisitions</button><button onClick={() => setMine(false)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}>All Requisitions</button></div>
      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Raise requisition</h2><button onClick={reset}><X size={18} className="text-slate-400" /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Title</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" /></div>
            <div><label className="label">From maintenance (optional)</label><select value={form.maintenance_id} onChange={(e) => { const m = (maintenance || []).find((x) => x.id === e.target.value); setForm({ ...form, maintenance_id: e.target.value, maintenance_type: m?.maintenance_type || form.maintenance_type, maintenance_cost: m ? String(m.total_cost) : form.maintenance_cost }); }} className="input"><option value="">—</option>{(maintenance || []).map((m) => <option key={m.id} value={m.id}>{m.facility_name} · {m.maintenance_type}</option>)}</select></div>
            <div><label className="label">Maintenance cost</label><input type="number" value={form.maintenance_cost} onChange={(e) => setForm({ ...form, maintenance_cost: e.target.value })} className="input" /></div>
            <div><label className="label">Requisition cost</label><input type="number" value={form.requisition_cost} onChange={(e) => setForm({ ...form, requisition_cost: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.title || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Raise</button></div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <div className="py-16 text-center text-slate-400 text-sm"><Receipt size={30} className="mx-auto mb-2 opacity-50" />No requisitions.</div>
          : (<table className="w-full text-left"><thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Ref", "Title", "Level", "Req. cost", "Approved", "Disbursed", "Status", ""].map((h) => (<th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">{rows.map((r) => (<tr key={r.id} className="hover:bg-slate-50/70">
              <td className="px-4 py-3 text-xs font-mono text-slate-500">{r.reference}</td>
              <td className="px-4 py-3 text-sm font-bold text-slate-900">{r.title}<p className="text-xs font-normal text-slate-400">{r.requester_name}</p></td>
              <td className="px-4 py-3 text-xs text-slate-500">{r.approval_level_name || "—"}</td>
              <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{Number(r.requisition_cost).toLocaleString()}</td>
              <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{Number(r.total_approved).toLocaleString()}</td>
              <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{Number(r.total_disbursed).toLocaleString()}</td>
              <td className="px-4 py-3"><span className={cn("badge capitalize", STATUS_STYLE[r.status])}>{r.status}</span></td>
              <td className="px-4 py-3">{canWrite && (
                <div className="flex items-center gap-2">
                  {r.status === "pending" && <button onClick={() => approve.mutate(r.id)} className="text-xs text-blue-600 font-semibold hover:underline inline-flex items-center gap-1"><CheckCircle2 size={13} />Approve</button>}
                  {r.status === "approved" && <button onClick={() => { if (confirm("Disburse this requisition?")) disburse.mutate(r.id); }} className="text-xs text-emerald-600 font-semibold hover:underline inline-flex items-center gap-1"><Banknote size={13} />Disburse</button>}
                </div>
              )}</td>
            </tr>))}</tbody></table>)}
      </div>
    </div>
  );
}
