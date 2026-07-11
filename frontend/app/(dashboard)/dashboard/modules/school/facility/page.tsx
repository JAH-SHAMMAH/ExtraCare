"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import {
  useFacilities, useSaveFacility, useDeleteFacility,
  useFacilityTypes, useSaveFacilityType, useDeleteFacilityType,
  useFacilityLocations, useSaveFacilityLocation, useDeleteFacilityLocation,
  useFacilityDepartments, useSaveFacilityDepartment, useDeleteFacilityDepartment,
} from "@/hooks/useFacility";
import { Building2, Plus, X, Loader2, Edit2, Trash2, Eye } from "lucide-react";
import type { FacilityItem, FacilityLookup, FacilityDepartment } from "@/types";

type Tab = "list" | "types" | "locations" | "departments";
const TABS: [Tab, string][] = [["list", "Facility List"], ["types", "Facility Types"], ["locations", "Facility Locations"], ["departments", "Facility Departments"]];

export default function FacilityManagementPage() {
  const [tab, setTab] = useState<Tab>("list");
  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Facility Management</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Management</h1>
        <p className="text-slate-500 text-sm mt-0.5">Facilities, types, locations and departments.</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200 mb-6 flex-wrap">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {tab === "list" ? <FacilityList /> : tab === "types" ? <LookupTab kind="type" /> : tab === "locations" ? <LookupTab kind="location" /> : <DepartmentsTab />}
    </div>
  );
}

function FacilityList() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const { data, isLoading } = useFacilities();
  const { data: types } = useFacilityTypes();
  const { data: locations } = useFacilityLocations();
  const save = useSaveFacility();
  const del = useDeleteFacility();
  const rows: FacilityItem[] = data || [];

  const BLANK = { name: "", facility_type_id: "", quantity: "1", notes: "", is_active: true, location_ids: [] as string[], manager_ids: [] as string[] };
  const [show, setShow] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState(BLANK);
  const [viewLoc, setViewLoc] = useState<FacilityItem | null>(null);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (f: FacilityItem) => {
    setForm({ name: f.name, facility_type_id: f.facility_type_id || "", quantity: String(f.quantity), notes: f.notes || "", is_active: f.is_active, location_ids: f.location_ids, manager_ids: f.manager_ids });
    setEditing(f.id); setShow(true);
  };
  const submit = () => {
    const payload = { name: form.name, facility_type_id: form.facility_type_id || null, quantity: Number(form.quantity) || 1, notes: form.notes || null, is_active: form.is_active, location_ids: form.location_ids, manager_ids: form.manager_ids };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };
  const toggleLoc = (id: string) => setForm((s) => ({ ...s, location_ids: s.location_ids.includes(id) ? s.location_ids.filter((x) => x !== id) : [...s.location_ids, id] }));

  return (
    <>
      {canWrite && <div className="flex justify-end mb-4">{!show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> Add Facility</button>}</div>}
      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit facility" : "New facility"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Type</label><select value={form.facility_type_id} onChange={(e) => setForm({ ...form, facility_type_id: e.target.value })} className="input"><option value="">—</option>{(types || []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
            <div><label className="label">Quantity</label><input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} className="input" /></div>
            <div className="flex items-center gap-2 mt-6"><input type="checkbox" id="fac-active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /><label htmlFor="fac-active" className="text-xs font-medium text-slate-700">Active</label></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-2">
              <label className="label">Assigned locations</label>
              <div className="flex flex-wrap gap-2">{(locations || []).map((l) => (<button key={l.id} type="button" onClick={() => toggleLoc(l.id)} className={cn("badge cursor-pointer", form.location_ids.includes(l.id) ? "bg-brand-50 text-brand-700 border-brand-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{l.name}</button>))}{(locations || []).length === 0 && <span className="text-xs text-slate-400">Add locations in the Facility Locations tab.</span>}</div>
            </div>
            <div className="md:col-span-2">
              <label className="label">Facility manager(s)</label>
              <EntityPicker type="staff" value={null} onChange={(id) => { if (id && !form.manager_ids.includes(id)) setForm((s) => ({ ...s, manager_ids: [...s.manager_ids, id] })); }} />
              <div className="flex flex-wrap gap-1 mt-2">{form.manager_ids.map((id) => (<span key={id} className="badge bg-slate-100 text-slate-600 border-slate-200 inline-flex items-center gap-1">{id.slice(0, 8)}<button onClick={() => setForm((s) => ({ ...s, manager_ids: s.manager_ids.filter((x) => x !== id) }))}><X size={10} /></button></span>))}</div>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <div className="py-16 text-center text-slate-400 text-sm"><Building2 size={30} className="mx-auto mb-2 opacity-50" />No facilities yet.</div>
          : (
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Facility", "Type", "Qty", "Locations", "Status", "Inspections", "Manager(s)", ""].map((h) => (<th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {rows.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 text-sm font-bold text-slate-900">{f.name}{f.notes && <p className="text-xs font-normal text-slate-400">{f.notes}</p>}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{f.facility_type_name || "—"}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{f.quantity}</td>
                    <td className="px-4 py-3 text-sm text-slate-600"><button onClick={() => setViewLoc(f)} className="inline-flex items-center gap-1 text-brand-600 hover:underline"><Eye size={12} />{f.location_names.length}</button></td>
                    <td className="px-4 py-3">{f.is_active ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">Active</span> : <span className="badge bg-slate-50 text-slate-400 border-slate-200">Inactive</span>}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{f.inspection_count}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{f.manager_names.join(", ") || "—"}</td>
                    <td className="px-4 py-3">{canWrite && (<div className="flex items-center gap-2"><button onClick={() => startEdit(f)} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={14} /></button><button onClick={() => { if (confirm(`Delete ${f.name}?`)) del.mutate(f.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button></div>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
      {viewLoc && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setViewLoc(null)}>
          <div className="bg-white rounded-2xl w-full max-w-sm p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-bold text-slate-900">{viewLoc.name} — locations</h2><button onClick={() => setViewLoc(null)}><X size={16} /></button></div>
            {viewLoc.location_names.length ? <ul className="text-sm text-slate-700 space-y-1">{viewLoc.location_names.map((n, i) => <li key={i}>• {n}</li>)}</ul> : <p className="text-sm text-slate-400">No locations assigned.</p>}
          </div>
        </div>
      )}
    </>
  );
}

function LookupTab({ kind }: { kind: "type" | "location" }) {
  const canWrite = useHasPermission("school_admin:facility:write");
  const typesQ = useFacilityTypes(); const typesSave = useSaveFacilityType(); const typesDel = useDeleteFacilityType();
  const locsQ = useFacilityLocations(); const locsSave = useSaveFacilityLocation(); const locsDel = useDeleteFacilityLocation();
  const q = kind === "type" ? typesQ : locsQ;
  const save = kind === "type" ? typesSave : locsSave;
  const del = kind === "type" ? typesDel : locsDel;
  const rows: FacilityLookup[] = q.data || [];
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const submit = () => save.mutate({ id: editing || undefined, data: { name } }, { onSuccess: () => { setName(""); setEditing(null); } });

  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex items-end gap-3">
          <div className="flex-1"><label className="label">{kind === "type" ? "Facility type" : "Location"} name</label><input value={name} onChange={(e) => setName(e.target.value)} className="input" /></div>
          <button onClick={submit} disabled={!name || save.isPending} className="btn-primary">{editing ? "Update" : "Add"}</button>
          {editing && <button onClick={() => { setName(""); setEditing(null); }} className="btn-secondary">Cancel</button>}
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {q.isLoading ? <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <p className="py-12 text-center text-slate-400 text-sm">None yet.</p>
          : rows.map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-5 py-3">
              <span className="text-sm font-semibold text-slate-800">{r.name}</span>
              {canWrite && <div className="ml-auto flex items-center gap-2"><button onClick={() => { setName(r.name); setEditing(r.id); }} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={13} /></button><button onClick={() => { if (confirm(`Delete ${r.name}?`)) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button></div>}
            </div>
          ))}
      </div>
    </>
  );
}

function DepartmentsTab() {
  const canWrite = useHasPermission("school_admin:facility:write");
  const { data, isLoading } = useFacilityDepartments();
  const save = useSaveFacilityDepartment();
  const del = useDeleteFacilityDepartment();
  const rows: FacilityDepartment[] = data || [];
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const submit = () => save.mutate({ id: editing || undefined, data: { name } }, { onSuccess: () => { setName(""); setEditing(null); } });
  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex items-end gap-3">
          <div className="flex-1"><label className="label">Department name</label><input value={name} onChange={(e) => setName(e.target.value)} className="input" /></div>
          <button onClick={submit} disabled={!name || save.isPending} className="btn-primary">{editing ? "Update" : "Add"}</button>
          {editing && <button onClick={() => { setName(""); setEditing(null); }} className="btn-secondary">Cancel</button>}
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {isLoading ? <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          : rows.length === 0 ? <p className="py-12 text-center text-slate-400 text-sm">None yet. Assign officers in Configuration.</p>
          : rows.map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-5 py-3">
              <span className="text-sm font-semibold text-slate-800">{r.name}</span>
              <span className="badge bg-slate-50 text-slate-500 border-slate-200">{r.officer_count} officer{r.officer_count === 1 ? "" : "s"}</span>
              {canWrite && <div className="ml-auto flex items-center gap-2"><button onClick={() => { setName(r.name); setEditing(r.id); }} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={13} /></button><button onClick={() => { if (confirm(`Delete ${r.name}?`)) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button></div>}
            </div>
          ))}
      </div>
    </>
  );
}
