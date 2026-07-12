"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useStudentPickups, useCreatePickup, useUpdatePickup, useDeletePickup,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { ArrowLeft, Plus, X, Loader2, ShieldCheck, Power, Edit2 } from "lucide-react";
import type { AuthorizedPickup } from "@/types";

const RELATIONSHIPS = ["parent", "guardian", "sibling", "driver", "relative", "other"];

const EMPTY = {
  student_id: "", full_name: "", relationship_type: "guardian",
  phone: "", id_document: "", photo_url: "",
};

export default function StudentPickupPage() {
  const canWrite = useHasPermission("school:students:write");
  const [activeOnly, setActiveOnly] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY });

  const { data, isLoading } = useStudentPickups({ active_only: activeOnly, page: 1, page_size: 100 });
  const create = useCreatePickup();
  const update = useUpdatePickup();
  const remove = useDeletePickup();
  const rows: AuthorizedPickup[] = data?.items || [];

  const reset = () => { setForm({ ...EMPTY }); setEditId(null); setShowForm(false); };

  const startEdit = (p: AuthorizedPickup) => {
    setForm({
      student_id: p.student_id, full_name: p.full_name,
      relationship_type: p.relationship_type || "guardian",
      phone: p.phone || "", id_document: p.id_document || "", photo_url: p.photo_url || "",
    });
    setEditId(p.id);
    setShowForm(true);
  };

  const submit = () => {
    const payload = {
      full_name: form.full_name, relationship_type: form.relationship_type || null,
      phone: form.phone || null, id_document: form.id_document || null,
      photo_url: form.photo_url || null,
    };
    if (editId) {
      update.mutate({ id: editId, data: payload }, { onSuccess: reset });
    } else {
      create.mutate({ ...payload, student_id: form.student_id }, { onSuccess: reset });
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/students" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Students</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Manage Students Pickup</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Students Pickup</h1>
          <p className="text-slate-500 text-sm mt-0.5">People authorised to collect a student from school.</p>
        </div>
        {canWrite && !showForm && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Authorise Pickup</button>}
      </div>

      <div className="mb-5">
        <label className="inline-flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} className="rounded border-slate-300" />
          Active authorisations only
        </label>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editId ? "Edit pickup authorisation" : "New pickup authorisation"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Student *</label>
              {/* Student is fixed once created — editing a person's details keeps them tied to the same child. */}
              <EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} disabled={!!editId} />
            </div>
            <div><label className="label">Authorised person *</label><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="input" placeholder="Full name" /></div>
            <div>
              <label className="label">Relationship</label>
              <select value={form.relationship_type} onChange={(e) => setForm({ ...form, relationship_type: e.target.value })} className="input capitalize">
                {RELATIONSHIPS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div><label className="label">Phone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input" placeholder="+234..." /></div>
            <div><label className="label">ID document <span className="text-slate-400 font-normal">(type / number)</span></label><input value={form.id_document} onChange={(e) => setForm({ ...form, id_document: e.target.value })} className="input" placeholder="e.g. National ID 1234..." /></div>
            <div><label className="label">Photo URL <span className="text-slate-400 font-normal">(optional)</span></label><input value={form.photo_url} onChange={(e) => setForm({ ...form, photo_url: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={(!editId && !form.student_id) || !form.full_name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">
              {(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />} {editId ? "Save" : "Authorise"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><ShieldCheck size={30} className="mx-auto mb-2 opacity-50" />No pickup authorisations yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">
              {["Student", "Authorised person", "Relationship", "Phone", "ID", "Status", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((p) => (
                <tr key={p.id} className={cn("hover:bg-slate-50/70", !p.is_active && "opacity-60")}>
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{p.student_name || p.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{p.full_name}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 capitalize">{p.relationship_type || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{p.phone || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{p.id_document || "—"}</td>
                  <td className="px-5 py-4">
                    <span className={cn("badge", p.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200")}>
                      {p.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-1 justify-end">
                        <button onClick={() => startEdit(p)} title="Edit" className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"><Edit2 size={14} /></button>
                        {p.is_active ? (
                          <button onClick={() => remove.mutate(p.id)} title="Deactivate" className="p-1.5 rounded hover:bg-rose-50 text-slate-400 hover:text-rose-600"><Power size={14} /></button>
                        ) : (
                          <button onClick={() => update.mutate({ id: p.id, data: { is_active: true } })} title="Re-activate" className="p-1.5 rounded hover:bg-emerald-50 text-slate-400 hover:text-emerald-600"><Power size={14} /></button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
