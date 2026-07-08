"use client";

import { useState } from "react";
import { useTeachers, useCreateTeacher, useUpdateTeacher, useDeleteTeacher } from "@/hooks/useSchool";
import { cn, formatDate, getInitials } from "@/lib/utils";
import { Search, UserPlus, UserCheck, MoreVertical, Edit2, Trash2, X, Loader2, Eye, Star } from "lucide-react";
import { toast } from "sonner";
import type { Teacher } from "@/types";

export default function TeachersPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [editingTeacher, setEditingTeacher] = useState<Teacher | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [viewTeacher, setViewTeacher] = useState<Teacher | null>(null);

  const { data, isLoading } = useTeachers({ page, page_size: 25, search: search || undefined });
  const createTeacher = useCreateTeacher();
  const updateTeacher = useUpdateTeacher();
  const deleteTeacher = useDeleteTeacher();

  const [form, setForm] = useState({
    first_name: "", last_name: "", email: "", phone: "",
    department: "", qualification: "", subjects: "",
  });

  const resetForm = () => {
    setForm({ first_name: "", last_name: "", email: "", phone: "", department: "", qualification: "", subjects: "" });
    setEditingTeacher(null);
    setShowForm(false);
  };

  const handleSubmit = () => {
    const missing: string[] = [];
    if (!form.first_name.trim()) missing.push("First Name");
    if (!form.last_name.trim()) missing.push("Last Name");
    // Cheap email sanity check so the backend's 422 isn't the first
    // signal the user gets for a typo. Full validation still lives server-side.
    if (!form.email.trim() || !form.email.includes("@")) missing.push("Email");
    if (missing.length) {
      toast.error(`Please fill: ${missing.join(", ")}`);
      return;
    }
    const payload = { ...form, subjects: form.subjects.split(",").map((s) => s.trim()).filter(Boolean) };
    if (editingTeacher) {
      updateTeacher.mutate({ id: editingTeacher.id, data: payload }, { onSuccess: resetForm });
    } else {
      createTeacher.mutate(payload, { onSuccess: resetForm });
    }
  };

  const handleEdit = (t: Teacher) => {
    setForm({
      first_name: t.first_name, last_name: t.last_name, email: t.email,
      phone: t.phone || "", department: t.department || "",
      qualification: t.qualification || "", subjects: t.subjects?.join(", ") || "",
    });
    setEditingTeacher(t);
    setShowForm(true);
    setMenuOpen(null);
  };

  const handleDelete = (id: string) => {
    if (confirm("Are you sure you want to remove this teacher?")) deleteTeacher.mutate(id);
    setMenuOpen(null);
  };

  const items = data?.items || [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Teachers</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Teacher Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Manage teaching staff, qualifications, and assignments.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2">
          <UserPlus size={15} /> Add Teacher
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Teachers", value: data?.total ?? "—" },
          { label: "Active", value: items.filter((t: Teacher) => t.is_active).length || "—" },
          { label: "Departments", value: [...new Set(items.map((t: Teacher) => t.department).filter(Boolean))].length || "—" },
          { label: "Subjects Covered", value: [...new Set(items.flatMap((t: Teacher) => t.subjects || []))].length || "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editingTeacher ? "Edit Teacher" : "New Teacher"}</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">First Name *</label><input required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="input" /></div>
            <div><label className="label">Last Name *</label><input required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="input" /></div>
            <div><label className="label">Email *</label><input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input" /></div>
            <div><label className="label">Phone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input" /></div>
            <div><label className="label">Department</label><input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="input" /></div>
            <div><label className="label">Qualification</label><input value={form.qualification} onChange={(e) => setForm({ ...form, qualification: e.target.value })} className="input" /></div>
            <div className="md:col-span-3"><label className="label">Subjects (comma-separated)</label><input value={form.subjects} onChange={(e) => setForm({ ...form, subjects: e.target.value })} placeholder="Mathematics, Physics, Chemistry" className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createTeacher.isPending || updateTeacher.isPending} className="btn-primary gap-2">
              {(createTeacher.isPending || updateTeacher.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editingTeacher ? "Update" : "Add Teacher"}
            </button>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search teachers..." className="input pl-9" />
        </div>
      </div>

      {/* View */}
      {viewTeacher && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">Teacher Details</h2>
            <button onClick={() => setViewTeacher(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div><p className="text-[10px] font-bold uppercase text-slate-400">Name</p><p className="text-sm font-medium text-slate-800">{viewTeacher.first_name} {viewTeacher.last_name}</p></div>
            <div><p className="text-[10px] font-bold uppercase text-slate-400">Email</p><p className="text-sm text-slate-800">{viewTeacher.email}</p></div>
            <div><p className="text-[10px] font-bold uppercase text-slate-400">Department</p><p className="text-sm text-slate-800">{viewTeacher.department || "—"}</p></div>
            <div><p className="text-[10px] font-bold uppercase text-slate-400">Qualification</p><p className="text-sm text-slate-800">{viewTeacher.qualification || "—"}</p></div>
            <div className="md:col-span-2"><p className="text-[10px] font-bold uppercase text-slate-400">Subjects</p><div className="flex flex-wrap gap-1 mt-1">{viewTeacher.subjects?.map((s) => (<span key={s} className="badge bg-brand-50 text-brand-700 border-brand-200">{s}</span>)) || "—"}</div></div>
            <div><p className="text-[10px] font-bold uppercase text-slate-400">Hired</p><p className="text-sm text-slate-800">{formatDate(viewTeacher.hire_date)}</p></div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Teacher", "Department", "Subjects", "Status", "Hired", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}><td colSpan={6} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>
            )) : items.length === 0 ? (
              <tr><td colSpan={6} className="px-5 py-16 text-center text-slate-400 text-sm">
                <UserCheck size={32} className="mx-auto mb-2 opacity-50" />No teachers found.
              </td></tr>
            ) : items.map((t: Teacher) => (
              <tr key={t.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-emerald-600/10 border border-emerald-100 flex items-center justify-center text-emerald-700 text-sm font-bold shrink-0">
                      {getInitials(`${t.first_name} ${t.last_name}`)}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900">{t.first_name} {t.last_name}</p>
                      <p className="text-xs text-slate-400">{t.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{t.department || "—"}</td>
                <td className="px-5 py-3.5">
                  <div className="flex flex-wrap gap-1">{t.subjects?.slice(0, 2).map((s) => (
                    <span key={s} className="badge bg-blue-50 text-blue-700 border-blue-200 text-[10px]">{s}</span>
                  ))}{(t.subjects?.length || 0) > 2 && <span className="text-[10px] text-slate-400">+{t.subjects!.length - 2}</span>}</div>
                </td>
                <td className="px-5 py-3.5">
                  <span className={cn("badge", t.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200")}>
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-xs text-slate-500">{formatDate(t.hire_date)}</td>
                <td className="px-5 py-3.5">
                  <div className="relative">
                    <button onClick={() => setMenuOpen(menuOpen === t.id ? null : t.id)} className="p-1 rounded hover:bg-slate-100"><MoreVertical size={14} className="text-slate-400" /></button>
                    {menuOpen === t.id && (
                      <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                        <button onClick={() => { setViewTeacher(t); setMenuOpen(null); }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"><Eye size={13} /> View</button>
                        <button onClick={() => handleEdit(t)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"><Edit2 size={13} /> Edit</button>
                        <button onClick={() => handleDelete(t.id)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"><Trash2 size={13} /> Delete</button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {data && data.total_pages > 1 && (
          <div className="px-5 py-4 border-t border-slate-100 flex items-center justify-between">
            <p className="text-xs text-slate-500">Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, data.total)} of {data.total}</p>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40">Prev</button>
              <button onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))} disabled={page === data.total_pages} className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
