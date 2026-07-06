"use client";

import { useState } from "react";
import {
  useHostels, useCreateHostel, useUpdateHostel, useDeleteHostel,
  useHostelAllocations, useAllocateBoarder, useDeallocateBoarder,
} from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { Loader2, Plus, X, Trash2, Edit2, AlertTriangle, BedDouble, ArrowLeft, UserPlus } from "lucide-react";
import type { Hostel } from "@/types";

const GENDERS = ["boys", "girls", "mixed"];

export default function HostelPage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [open, setOpen] = useState<Hostel | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Hostel | null>(null);
  const [form, setForm] = useState({ name: "", gender: "", capacity: "", warden_id: "", notes: "" });

  const { data, isLoading, isError, refetch } = useHostels();
  const create = useCreateHostel();
  const update = useUpdateHostel();
  const remove = useDeleteHostel();

  const reset = () => { setForm({ name: "", gender: "", capacity: "", warden_id: "", notes: "" }); setEditing(null); setShowForm(false); };
  const openEdit = (h: Hostel) => {
    setForm({ name: h.name, gender: h.gender ?? "", capacity: h.capacity?.toString() ?? "", warden_id: h.warden_id ?? "", notes: h.notes ?? "" });
    setEditing(h); setShowForm(true);
  };
  const submit = () => {
    const payload = { name: form.name.trim(), gender: form.gender || null, capacity: form.capacity ? Number(form.capacity) : null, warden_id: form.warden_id || null, notes: form.notes || null };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    else create.mutate(payload, { onSuccess: reset });
  };

  if (open) return <AllocationsView hostel={open} canWrite={canWrite} onBack={() => setOpen(null)} />;

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral &amp; Welfare</span><span>/</span><span className="text-brand-600 font-semibold">Hostel / Boarding</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Hostel / Boarding</h1>
          <p className="text-slate-500 text-sm mt-0.5">Boarding houses and bed allocation.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Hostel</button>}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Hostel" : "New Hostel"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Gender</label><select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} className="input capitalize"><option value="">—</option>{GENDERS.map((g) => <option key={g} value={g}>{g}</option>)}</select></div>
            <div><label className="label">Capacity</label><input type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} className="input" /></div>
            <div><label className="label">Warden</label><EntityPicker type="staff" value={form.warden_id || null} onChange={(id) => setForm({ ...form, warden_id: id || "" })} /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Update" : "Create"}</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-36 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load hostels.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows && rows.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((h) => (
            <div key={h.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-bold text-slate-900">{h.name}</h3>
                {canWrite && (
                  <div className="flex items-center gap-1">
                    <button onClick={() => openEdit(h)} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={13} /></button>
                    <button onClick={() => { if (confirm("Delete this hostel?")) remove.mutate(h.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>
                  </div>
                )}
              </div>
              <p className="text-xs text-slate-500 capitalize mb-3">{h.gender || "—"}{h.warden_name ? ` · Warden: ${h.warden_name}` : ""}</p>
              <div className="flex items-center justify-between text-sm mb-3">
                <span className="text-slate-500">Occupancy</span>
                <span className="font-bold text-slate-800">{h.occupancy}{h.capacity ? ` / ${h.capacity}` : ""}</span>
              </div>
              <button onClick={() => setOpen(h)} className="w-full text-xs font-semibold text-brand-600 hover:text-brand-700 border-t border-slate-100 pt-3">Manage boarders →</button>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><BedDouble size={36} className="mb-3 opacity-40" /><p className="font-semibold">No hostels yet</p></div>
      )}
    </div>
  );
}

function AllocationsView({ hostel, canWrite, onBack }: { hostel: Hostel; canWrite: boolean; onBack: () => void }) {
  const { data: allocs, isLoading } = useHostelAllocations(hostel.id);
  const allocate = useAllocateBoarder();
  const deallocate = useDeallocateBoarder();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ student_id: "", room: "", bed: "" });

  const add = () => allocate.mutate(
    { student_id: form.student_id, hostel_id: hostel.id, room: form.room || null, bed: form.bed || null },
    { onSuccess: () => { setForm({ student_id: "", room: "", bed: "" }); setShow(false); } },
  );

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to hostels</button>
      <div className="flex items-end justify-between mb-6">
        <div><h1 className="text-2xl font-black text-slate-900">{hostel.name}</h1><p className="text-sm text-slate-500 mt-1">{allocs?.length ?? 0} boarders</p></div>
        {canWrite && <button onClick={() => setShow((s) => !s)} className="btn-primary gap-2"><UserPlus size={15} /> Allocate Boarder</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div className="md:col-span-2"><label className="label">Student</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
          <div><label className="label">Room</label><input value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} className="input" /></div>
          <div><label className="label">Bed</label><input value={form.bed} onChange={(e) => setForm({ ...form, bed: e.target.value })} className="input" /></div>
          <button onClick={add} disabled={!form.student_id || allocate.isPending} className="btn-primary gap-2 justify-center md:col-span-4">{allocate.isPending && <Loader2 size={14} className="animate-spin" />}Allocate</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Room", "Bed", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => <tr key={i}>{Array.from({ length: 4 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : allocs && allocs.length > 0 ? (
              allocs.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm text-slate-700">{a.student_name || a.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{a.room || "—"}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{a.bed || "—"}</td>
                  <td className="px-5 py-3">{canWrite && <button onClick={() => deallocate.mutate(a.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={4} className="py-10 text-center text-slate-400 text-sm">No boarders allocated.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
