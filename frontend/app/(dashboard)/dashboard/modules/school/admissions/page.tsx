"use client";

import { useState } from "react";
import {
  useApplications, useCreateApplication, useUpdateApplication,
  useDeleteApplication, useAdmitApplication, useClassOptions,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  Contact, Plus, X, Loader2, Edit2, Trash2, AlertTriangle, Search, UserPlus, CheckCircle2,
} from "lucide-react";
import type { AdmissionApplication } from "@/types";

const STATUSES = ["enquiry", "applied", "screening", "offered", "admitted", "rejected", "withdrawn"];
const STATUS_STYLE: Record<string, string> = {
  enquiry: "bg-slate-50 text-slate-600 border-slate-200",
  applied: "bg-blue-50 text-blue-700 border-blue-200",
  screening: "bg-indigo-50 text-indigo-700 border-indigo-200",
  offered: "bg-amber-50 text-amber-700 border-amber-200",
  admitted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
  withdrawn: "bg-slate-50 text-slate-400 border-slate-200",
};

const EMPTY = {
  first_name: "", last_name: "", date_of_birth: "", gender: "",
  guardian_name: "", guardian_phone: "", guardian_email: "",
  applying_for_class_id: "", applying_for_level: "", source: "", status: "enquiry", notes: "",
};

export default function AdmissionsPage() {
  const canWrite = useHasPermission("school:admissions:write");
  const canAdmit = useHasPermission("school:students:write");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<AdmissionApplication | null>(null);
  const [form, setForm] = useState({ ...EMPTY });

  const params: { status?: string; search?: string } = {};
  if (statusFilter) params.status = statusFilter;
  if (search.trim()) params.search = search.trim();
  const { data, isLoading, isError, refetch } = useApplications(Object.keys(params).length ? params : undefined);
  const { data: classData } = useClassOptions();
  const createApp = useCreateApplication();
  const updateApp = useUpdateApplication();
  const deleteApp = useDeleteApplication();
  const admit = useAdmitApplication();

  const classes = (classData?.items ?? []) as Array<{ id: string; name: string }>;

  const reset = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(false); };
  const openNew = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(true); };
  const openEdit = (a: AdmissionApplication) => {
    setForm({
      first_name: a.first_name, last_name: a.last_name,
      date_of_birth: a.date_of_birth ?? "", gender: a.gender ?? "",
      guardian_name: a.guardian_name ?? "", guardian_phone: a.guardian_phone ?? "", guardian_email: a.guardian_email ?? "",
      applying_for_class_id: a.applying_for_class_id ?? "", applying_for_level: a.applying_for_level ?? "",
      source: a.source ?? "", status: a.status, notes: a.notes ?? "",
    });
    setEditing(a);
    setShowForm(true);
  };

  const submit = () => {
    const payload = {
      first_name: form.first_name.trim(), last_name: form.last_name.trim(),
      date_of_birth: form.date_of_birth || null, gender: form.gender || null,
      guardian_name: form.guardian_name || null, guardian_phone: form.guardian_phone || null,
      guardian_email: form.guardian_email || null,
      applying_for_class_id: form.applying_for_class_id || null,
      applying_for_level: form.applying_for_level || null,
      source: form.source || null, status: form.status, notes: form.notes || null,
    };
    if (editing) updateApp.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    else createApp.mutate(payload, { onSuccess: reset });
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Admissions &amp; Enquiries</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Admissions &amp; Enquiries</h1>
          <p className="text-slate-500 text-sm mt-0.5">Prospective student pipeline — enquiry to admission.</p>
        </div>
        {canWrite && <button onClick={openNew} className="btn-primary gap-2"><Plus size={15} /> New Application</button>}
      </div>

      <div className="flex flex-wrap gap-3 mb-5">
        <div className="relative max-w-xs flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search applicant or guardian…" className="input pl-9" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Application" : "New Application"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">First Name *</label><input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="input" /></div>
            <div><label className="label">Last Name *</label><input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="input" /></div>
            <div><label className="label">Date of Birth</label><input type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} className="input" /></div>
            <div><label className="label">Gender</label>
              <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} className="input">
                <option value="">—</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
              </select>
            </div>
            <div><label className="label">Applying for Class</label>
              <select value={form.applying_for_class_id} onChange={(e) => setForm({ ...form, applying_for_class_id: e.target.value })} className="input">
                <option value="">—</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div><label className="label">Level (if no class)</label><input value={form.applying_for_level} onChange={(e) => setForm({ ...form, applying_for_level: e.target.value })} className="input" placeholder="e.g. Primary 1" /></div>
            <div><label className="label">Guardian Name</label><input value={form.guardian_name} onChange={(e) => setForm({ ...form, guardian_name: e.target.value })} className="input" /></div>
            <div><label className="label">Guardian Phone</label><input value={form.guardian_phone} onChange={(e) => setForm({ ...form, guardian_phone: e.target.value })} className="input" /></div>
            <div><label className="label">Guardian Email</label><input value={form.guardian_email} onChange={(e) => setForm({ ...form, guardian_email: e.target.value })} className="input" /></div>
            <div><label className="label">Source</label><input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="input" placeholder="walk-in / referral / online" /></div>
            <div><label className="label">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.first_name.trim() || !form.last_name.trim() || createApp.isPending || updateApp.isPending} className="btn-primary gap-2">
              {(createApp.isPending || updateApp.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Applicant", "Class / Level", "Guardian", "Status", "Created", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>
              ))
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center">
                <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
                <p className="text-sm font-semibold text-slate-600">Couldn’t load applications.</p>
                <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
              </td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4">
                    <p className="text-sm font-semibold text-slate-800">{a.full_name}</p>
                    <p className="text-xs text-slate-400">{a.source || "—"}</p>
                  </td>
                  <td className="px-5 py-4"><span className="text-sm text-slate-600">{a.applying_for_class_name || a.applying_for_level || "—"}</span></td>
                  <td className="px-5 py-4">
                    <p className="text-sm text-slate-700">{a.guardian_name || "—"}</p>
                    <p className="text-xs text-slate-400">{a.guardian_phone || a.guardian_email || ""}</p>
                  </td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[a.status] || "")}>{a.status}</span></td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{formatDate(a.created_at)}</span></td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {canAdmit && !a.admitted_student_id && a.status !== "rejected" && a.status !== "withdrawn" && (
                        <button
                          onClick={() => { if (confirm(`Admit ${a.full_name} and add them to the student roster?`)) admit.mutate({ id: a.id }); }}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"
                          title="Admit → create student"
                        >
                          <UserPlus size={13} /> Admit
                        </button>
                      )}
                      {a.admitted_student_id && (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-600" title="Admitted"><CheckCircle2 size={13} /> Admitted</span>
                      )}
                      {canWrite && (
                        <>
                          <button onClick={() => openEdit(a)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                          <button onClick={() => { if (confirm("Delete this application?")) deleteApp.mutate(a.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400">
                <Contact size={36} className="mx-auto mb-3 opacity-40" />
                <p className="font-semibold">No applications yet</p>
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
