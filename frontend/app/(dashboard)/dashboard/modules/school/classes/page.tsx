"use client";

import { useState } from "react";
import { useClasses, useCreateClass, useUpdateClass, useDeleteClass } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { Search, Plus, School, MoreVertical, Edit2, Trash2, X, Loader2, Users2 } from "lucide-react";
import type { SchoolClass } from "@/types";

export default function ClassesPage() {
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingClass, setEditingClass] = useState<SchoolClass | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const { data, isLoading } = useClasses({ search: search || undefined });
  const createClass = useCreateClass();
  const updateClass = useUpdateClass();
  const deleteClass = useDeleteClass();

  const [form, setForm] = useState({ name: "", grade_level: "", section: "", capacity: "30", academic_year: new Date().getFullYear().toString() });

  const resetForm = () => { setForm({ name: "", grade_level: "", section: "", capacity: "30", academic_year: new Date().getFullYear().toString() }); setEditingClass(null); setShowForm(false); };

  const handleSubmit = () => {
    const payload = { ...form, capacity: parseInt(form.capacity) || 30 };
    if (editingClass) updateClass.mutate({ id: editingClass.id, data: payload }, { onSuccess: resetForm });
    else createClass.mutate(payload, { onSuccess: resetForm });
  };

  const handleEdit = (c: SchoolClass) => {
    setForm({ name: c.name, grade_level: c.grade_level || "", section: c.section || "", capacity: String(c.capacity), academic_year: c.academic_year });
    setEditingClass(c); setShowForm(true); setMenuOpen(null);
  };

  const items = data?.items || (Array.isArray(data) ? data : []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Classes</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Class Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Create and manage class groups and sections.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Class</button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editingClass ? "Edit Class" : "New Class"}</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Class Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. JSS 1A" className="input" /></div>
            <div><label className="label">Grade Level</label><input value={form.grade_level} onChange={(e) => setForm({ ...form, grade_level: e.target.value })} placeholder="e.g. JSS 1" className="input" /></div>
            <div><label className="label">Section</label><input value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} placeholder="e.g. A" className="input" /></div>
            <div><label className="label">Capacity</label><input type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} className="input" /></div>
            <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createClass.isPending || updateClass.isPending} className="btn-primary gap-2">
              {(createClass.isPending || updateClass.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editingClass ? "Update" : "Create Class"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
        <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search classes..." className="input pl-9" /></div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-32 bg-white rounded-xl border border-slate-200 animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-20 flex flex-col items-center text-slate-400">
          <School size={40} className="mb-3 opacity-40" /><p className="font-semibold">No classes found</p><p className="text-sm mt-1">Create your first class to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {items.map((c: SchoolClass) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center"><School size={18} className="text-purple-600" /></div>
                <div className="relative">
                  <button onClick={() => setMenuOpen(menuOpen === c.id ? null : c.id)} className="p-1 rounded hover:bg-slate-100"><MoreVertical size={14} className="text-slate-400" /></button>
                  {menuOpen === c.id && (
                    <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                      <button onClick={() => handleEdit(c)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"><Edit2 size={13} /> Edit</button>
                      <button onClick={() => { deleteClass.mutate(c.id); setMenuOpen(null); }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"><Trash2 size={13} /> Delete</button>
                    </div>
                  )}
                </div>
              </div>
              <h3 className="text-sm font-bold text-slate-900">{c.name}</h3>
              {c.grade_level && <p className="text-xs text-slate-500 mt-0.5">Grade: {c.grade_level}{c.section ? ` - ${c.section}` : ""}</p>}
              <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                <span className="flex items-center gap-1"><Users2 size={12} /> {c.student_count}/{c.capacity}</span>
                {c.class_teacher_name && <span>Teacher: {c.class_teacher_name}</span>}
              </div>
              <div className="mt-3 w-full bg-slate-100 rounded-full h-1.5">
                <div className={cn("h-full rounded-full", c.student_count >= c.capacity ? "bg-red-500" : c.student_count >= c.capacity * 0.8 ? "bg-orange-500" : "bg-brand-600")} style={{ width: `${Math.min((c.student_count / c.capacity) * 100, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
