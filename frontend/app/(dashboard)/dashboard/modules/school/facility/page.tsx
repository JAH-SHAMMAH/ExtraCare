"use client";

import { useState } from "react";
import {
  useFacilities, useCreateFacility, useUpdateFacility, useDeleteFacility,
  useFacilityBookings, useBookFacility, useCancelBooking,
} from "@/hooks/useOperations";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { Building2, Plus, X, Loader2, Trash2, Edit2, AlertTriangle, ArrowLeft, CalendarPlus, Ban } from "lucide-react";
import type { Facility } from "@/types";

const STATUSES = ["available", "maintenance", "unavailable"];
const STATUS_STYLE: Record<string, string> = {
  available: "bg-emerald-50 text-emerald-700 border-emerald-200",
  maintenance: "bg-amber-50 text-amber-700 border-amber-200",
  unavailable: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function FacilityPage() {
  const canWrite = useHasPermission("school_admin:write");
  const { data, isLoading, isError, refetch } = useFacilities();
  const create = useCreateFacility();
  const update = useUpdateFacility();
  const del = useDeleteFacility();
  const [open, setOpen] = useState<Facility | null>(null);
  const [show, setShow] = useState(false);
  const [editing, setEditing] = useState<Facility | null>(null);
  const [form, setForm] = useState({ name: "", type: "", capacity: "", location: "", status: "available", notes: "" });

  const reset = () => { setForm({ name: "", type: "", capacity: "", location: "", status: "available", notes: "" }); setEditing(null); setShow(false); };
  const openEdit = (f: Facility) => { setForm({ name: f.name, type: f.type ?? "", capacity: f.capacity?.toString() ?? "", location: f.location ?? "", status: f.status, notes: f.notes ?? "" }); setEditing(f); setShow(true); };
  const submit = () => {
    const payload = { name: form.name.trim(), type: form.type || null, capacity: form.capacity ? Number(form.capacity) : null, location: form.location || null, status: form.status, notes: form.notes || null };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    else create.mutate(payload, { onSuccess: reset });
  };

  if (open) return <BookingsView facility={open} canWrite={canWrite} onBack={() => setOpen(null)} />;

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Operations</span><span>/</span><span className="text-brand-600 font-semibold">Facility Management</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Facility Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Halls, labs and rooms — with double-booking protection.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Facility</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Facility" : "New Facility"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2"><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Type</label><input value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="input" placeholder="hall / lab / field" /></div>
            <div><label className="label">Capacity</label><input type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} className="input" /></div>
            <div><label className="label">Location</label><input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="input" /></div>
            <div><label className="label">Status</label><select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
            <div className="md:col-span-3"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Update" : "Create"}</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-36 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load facilities.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows && rows.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((f) => (
            <div key={f.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-bold text-slate-900">{f.name}</h3>
                <span className={cn("badge capitalize", STATUS_STYLE[f.status] || "")}>{f.status}</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">{[f.type, f.location, f.capacity ? `cap. ${f.capacity}` : null].filter(Boolean).join(" · ") || "—"}</p>
              <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                <button onClick={() => setOpen(f)} className="text-xs font-semibold text-brand-600 hover:text-brand-700">Bookings →</button>
                {canWrite && (
                  <div className="flex items-center gap-1">
                    <button onClick={() => openEdit(f)} className="text-slate-400 hover:text-brand-600 p-1"><Edit2 size={13} /></button>
                    <button onClick={() => { if (confirm("Delete this facility?")) del.mutate(f.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Building2 size={36} className="mb-3 opacity-40" /><p className="font-semibold">No facilities yet</p></div>
      )}
    </div>
  );
}

function BookingsView({ facility, canWrite, onBack }: { facility: Facility; canWrite: boolean; onBack: () => void }) {
  const { data: bookings, isLoading } = useFacilityBookings(facility.id);
  const book = useBookFacility();
  const cancel = useCancelBooking();
  const [form, setForm] = useState({ title: "", start_at: "", end_at: "", purpose: "" });

  const add = () => book.mutate({ id: facility.id, data: { title: form.title.trim(), start_at: form.start_at, end_at: form.end_at, purpose: form.purpose || null } },
    { onSuccess: () => setForm({ title: "", start_at: "", end_at: "", purpose: "" }) });

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to facilities</button>
      <h1 className="text-2xl font-black text-slate-900">{facility.name}</h1>
      <p className="text-sm text-slate-500 mt-1 mb-6">Bookings — overlaps are blocked automatically.</p>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div className="md:col-span-2"><label className="label">Title *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" /></div>
          <div><label className="label">Start *</label><input type="datetime-local" value={form.start_at} onChange={(e) => setForm({ ...form, start_at: e.target.value })} className="input" /></div>
          <div><label className="label">End *</label><input type="datetime-local" value={form.end_at} onChange={(e) => setForm({ ...form, end_at: e.target.value })} className="input" /></div>
          <button onClick={add} disabled={!form.title.trim() || !form.start_at || !form.end_at || book.isPending} className="btn-primary gap-2 justify-center md:col-span-4">{book.isPending ? <Loader2 size={14} className="animate-spin" /> : <CalendarPlus size={14} />}Book</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Title", "Start", "End", "Status", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : bookings && bookings.length > 0 ? (
              bookings.map((b) => (
                <tr key={b.id} className={cn("hover:bg-slate-50/70", b.status === "cancelled" && "opacity-50")}>
                  <td className="px-5 py-3 text-sm font-medium text-slate-800">{b.title}</td>
                  <td className="px-5 py-3 text-xs text-slate-500">{new Date(b.start_at).toLocaleString()}</td>
                  <td className="px-5 py-3 text-xs text-slate-500">{new Date(b.end_at).toLocaleString()}</td>
                  <td className="px-5 py-3"><span className={cn("badge capitalize", b.status === "cancelled" ? "bg-slate-50 text-slate-400 border-slate-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>{b.status}</span></td>
                  <td className="px-5 py-3">{canWrite && b.status === "booked" && <button onClick={() => cancel.mutate(b.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700"><Ban size={13} /> Cancel</button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-10 text-center text-slate-400 text-sm">No bookings yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
