"use client";

import { useState } from "react";
import { useSubjects, useCreateSubject, useUpdateSubject } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { BookMarked, Plus, Search, X, Loader2, MoreVertical, Edit2 } from "lucide-react";
import type { Subject } from "@/types";

export default function SubjectsPage() {
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Subject | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const { data, isLoading } = useSubjects({ search: search || undefined });
  const createSubject = useCreateSubject();
  const updateSubject = useUpdateSubject();

  const [form, setForm] = useState({ name: "", code: "", department: "", credit_hours: "1", teacher_name: "" });

  const resetForm = () => { setForm({ name: "", code: "", department: "", credit_hours: "1", teacher_name: "" }); setEditing(null); setShowForm(false); };

  const handleSubmit = () => {
    const payload = { ...form, credit_hours: parseInt(form.credit_hours) || 1 };
    if (editing) updateSubject.mutate({ id: editing.id, data: payload }, { onSuccess: resetForm });
    else createSubject.mutate(payload, { onSuccess: resetForm });
  };

  const handleEdit = (s: Subject) => {
    setForm({ name: s.name, code: s.code, department: s.department || "", credit_hours: String(s.credit_hours), teacher_name: s.teacher_name || "" });
    setEditing(s); setShowForm(true); setMenuOpen(null);
  };

  const items = data?.items || (Array.isArray(data) ? data : []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Subjects</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Subject Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Manage curriculum subjects and assign to classes.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Add Subject</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        {[{ label: "Total Subjects", value: items.length || "—" }, { label: "Active", value: items.filter((s: Subject) => s.is_active).length || "—" }, { label: "Departments", value: [...new Set(items.map((s: Subject) => s.department).filter(Boolean))].length || "—" }].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4"><p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p><p className="text-xl font-black text-slate-900">{value}</p></div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Subject" : "New Subject"}</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Subject Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Mathematics" className="input" /></div>
            <div><label className="label">Code *</label><input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="e.g. MTH101" className="input" /></div>
            <div><label className="label">Department</label><input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="input" /></div>
            <div><label className="label">Credit Hours</label><input type="number" min="1" value={form.credit_hours} onChange={(e) => setForm({ ...form, credit_hours: e.target.value })} className="input" /></div>
            <div><label className="label">Teacher</label><input value={form.teacher_name} onChange={(e) => setForm({ ...form, teacher_name: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createSubject.isPending || updateSubject.isPending} className="btn-primary gap-2">
              {(createSubject.isPending || updateSubject.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Update" : "Add Subject"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
        <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search subjects..." className="input pl-9" /></div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">
            {["Subject", "Code", "Department", "Teacher", "Credits", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}
          </tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => (<tr key={i}><td colSpan={7} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : items.length === 0 ? (<tr><td colSpan={7} className="px-5 py-16 text-center text-slate-400 text-sm"><BookMarked size={32} className="mx-auto mb-2 opacity-50" />No subjects found.</td></tr>)
            : items.map((s: Subject) => (
              <tr key={s.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="px-5 py-3.5"><div className="flex items-center gap-3"><div className="w-9 h-9 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-700 text-sm font-bold"><BookMarked size={14} /></div><p className="text-sm font-bold text-slate-900">{s.name}</p></div></td>
                <td className="px-5 py-3.5 text-xs font-mono text-slate-600">{s.code}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{s.department || "—"}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{s.teacher_name || "—"}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{s.credit_hours}</td>
                <td className="px-5 py-3.5"><span className={cn("badge", s.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200")}>{s.is_active ? "Active" : "Inactive"}</span></td>
                <td className="px-5 py-3.5">
                  <div className="relative">
                    <button onClick={() => setMenuOpen(menuOpen === s.id ? null : s.id)} className="p-1 rounded hover:bg-slate-100"><MoreVertical size={14} className="text-slate-400" /></button>
                    {menuOpen === s.id && (<div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                      <button onClick={() => handleEdit(s)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"><Edit2 size={13} /> Edit</button>
                    </div>)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
