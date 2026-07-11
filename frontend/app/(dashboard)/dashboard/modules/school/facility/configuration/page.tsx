"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import {
  useApprovalLevels, useSaveApprovalLevel, useDeleteApprovalLevel,
  useFacilityStaff, useSaveFacilityStaff, useDeleteFacilityStaff,
} from "@/hooks/useFacility";
import { ArrowLeft, Plus, X, Loader2, Edit2, Trash2 } from "lucide-react";
import type { FacilityApprovalLevel, FacilityStaffMember } from "@/types";

type Tab = "levels" | "facility_manager" | "requisition_manager" | "store_keeper";
const TABS: [Tab, string][] = [["levels", "Approval Levels"], ["facility_manager", "Facility Managers"], ["requisition_manager", "Requisition Managers"], ["store_keeper", "Store Keepers"]];

export default function FacilityConfigurationPage() {
  const [tab, setTab] = useState<Tab>("levels");
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/facility" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Facility Management</Link>
      <div className="mb-5"><nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span><span>/</span><span className="text-brand-600 font-semibold">Configuration</span></nav><h1 className="text-2xl font-black text-slate-900 tracking-tight">Configuration</h1></div>
      <div className="flex gap-1 border-b border-slate-200 mb-6 flex-wrap">{TABS.map(([k, l]) => (<button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>))}</div>
      {tab === "levels" ? <ApprovalLevels /> : <RolePool key={tab} role={tab} label={TABS.find((t) => t[0] === tab)![1]} />}
    </div>
  );
}

function ApprovalLevels() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const { data, isLoading } = useApprovalLevels();
  const save = useSaveApprovalLevel();
  const del = useDeleteApprovalLevel();
  const rows: FacilityApprovalLevel[] = data || [];
  const BLANK = { name: "", threshold: "0", handler_id: "", is_active: true };
  const [form, setForm] = useState(BLANK);
  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const submit = () => save.mutate({ id: editing || undefined, data: { name: form.name, threshold: Number(form.threshold) || 0, handler_id: form.handler_id || null, is_active: form.is_active } }, { onSuccess: reset });

  return (
    <>
      {canWrite && !show && <div className="flex justify-end mb-4"><button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Add level</button></div>}
      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Basic Expense Level" /></div>
            <div><label className="label">Threshold (min cost)</label><input type="number" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Handler (optional)</label><EntityPicker type="staff" value={form.handler_id || null} onChange={(id) => setForm({ ...form, handler_id: id || "" })} /></div>
            <div className="flex items-center gap-2"><input type="checkbox" id="lv-active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /><label htmlFor="lv-active" className="text-xs font-medium text-slate-700">Active</label></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <p className="py-12 text-center text-slate-400 text-sm">No approval levels. Requisitions route to the level whose threshold their cost meets.</p>
          : (<table className="w-full text-left"><thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Name", "Threshold", "Handler", "Status", ""].map((h) => (<th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">{rows.map((lv) => (<tr key={lv.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-3 text-sm font-bold text-slate-900">{lv.name}</td>
              <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{Number(lv.threshold).toLocaleString()}</td>
              <td className="px-5 py-3 text-xs text-slate-500">{lv.handler_name || "—"}</td>
              <td className="px-5 py-3">{lv.is_active ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Active</span> : <span className="badge bg-slate-50 text-slate-400 border-slate-200">Inactive</span>}</td>
              <td className="px-5 py-3">{canWrite && <div className="flex items-center gap-2"><button onClick={() => { setForm({ name: lv.name, threshold: String(lv.threshold), handler_id: lv.handler_id || "", is_active: lv.is_active }); setEditing(lv.id); setShow(true); }} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={13} /></button><button onClick={() => { if (confirm(`Delete ${lv.name}?`)) del.mutate(lv.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button></div>}</td>
            </tr>))}</tbody></table>)}
      </div>
    </>
  );
}

function RolePool({ role, label }: { role: string; label: string }) {
  const canWrite = useHasPermission("school_admin:facility:write");
  const { data, isLoading } = useFacilityStaff(role);
  const save = useSaveFacilityStaff();
  const del = useDeleteFacilityStaff();
  const rows: FacilityStaffMember[] = data || [];
  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4">
          <label className="label">Assign a user as {label.replace(/s$/, "")}</label>
          <EntityPicker type="staff" value={null} onChange={(id) => { if (id) save.mutate({ user_id: id, role_type: role }); }} />
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {isLoading ? <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <p className="py-12 text-center text-slate-400 text-sm">No {label.toLowerCase()} assigned.</p>
          : rows.map((s) => (<div key={s.id} className="flex items-center gap-3 px-5 py-3"><span className="text-sm font-semibold text-slate-800">{s.user_name || s.user_id.slice(0, 8)}</span>{canWrite && <button onClick={() => del.mutate(s.id)} className="ml-auto text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>}</div>))}
      </div>
    </>
  );
}
