"use client";

import { useState } from "react";
import Link from "next/link";
import {
  usePostEntranceForms, useCreatePostEntrance, useUpdatePostEntrance,
  useApplications, useClassOptions,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { ArrowLeft, Plus, X, Loader2, FileText } from "lucide-react";
import type { PostEntranceForm, AdmissionApplication } from "@/types";

const STATUSES = ["draft", "submitted", "reviewed"];
const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-50 text-slate-600 border-slate-200",
  submitted: "bg-blue-50 text-blue-700 border-blue-200",
  reviewed: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

// All editable string fields, grouped for the form layout.
const SECTIONS: { title: string; fields: [keyof FormState, string][] }[] = [
  { title: "Candidate", fields: [
    ["full_name", "Full name"], ["date_of_birth", "Date of birth"], ["gender", "Gender"],
    ["nationality", "Nationality"], ["state_origin", "State of origin"], ["lga", "LGA"],
    ["religion", "Religion"], ["previous_school", "Previous school"],
    ["applying_for_level", "Applying for level"], ["passport_photo_url", "Passport photo URL"],
    ["home_address", "Home address"],
  ] },
  { title: "Health", fields: [
    ["blood_group", "Blood group"], ["genotype", "Genotype"],
    ["allergies", "Allergies"], ["special_needs", "Special needs"],
  ] },
  { title: "Father", fields: [
    ["father_name", "Name"], ["father_occupation", "Occupation"],
    ["father_phone", "Phone"], ["father_email", "Email"],
  ] },
  { title: "Mother", fields: [
    ["mother_name", "Name"], ["mother_occupation", "Occupation"],
    ["mother_phone", "Phone"], ["mother_email", "Email"],
  ] },
  { title: "Guardian (if different)", fields: [
    ["guardian_name", "Name"], ["guardian_relationship", "Relationship"],
    ["guardian_phone", "Phone"], ["guardian_address", "Address"],
  ] },
  { title: "Emergency contact", fields: [
    ["emergency_name", "Name"], ["emergency_relationship", "Relationship"], ["emergency_phone", "Phone"],
  ] },
];

type FormState = {
  full_name: string; date_of_birth: string; gender: string; nationality: string;
  state_origin: string; lga: string; religion: string; home_address: string;
  passport_photo_url: string; previous_school: string; applying_for_level: string;
  applying_for_class_id: string;
  blood_group: string; genotype: string; allergies: string; special_needs: string;
  father_name: string; father_occupation: string; father_phone: string; father_email: string;
  mother_name: string; mother_occupation: string; mother_phone: string; mother_email: string;
  guardian_name: string; guardian_relationship: string; guardian_phone: string; guardian_address: string;
  emergency_name: string; emergency_relationship: string; emergency_phone: string;
  status: string;
};

const EMPTY: FormState = {
  full_name: "", date_of_birth: "", gender: "", nationality: "", state_origin: "", lga: "",
  religion: "", home_address: "", passport_photo_url: "", previous_school: "", applying_for_level: "",
  applying_for_class_id: "", blood_group: "", genotype: "", allergies: "", special_needs: "",
  father_name: "", father_occupation: "", father_phone: "", father_email: "",
  mother_name: "", mother_occupation: "", mother_phone: "", mother_email: "",
  guardian_name: "", guardian_relationship: "", guardian_phone: "", guardian_address: "",
  emergency_name: "", emergency_relationship: "", emergency_phone: "", status: "draft",
};

// Multi-line fields render as a textarea; the rest as inputs (dates get type=date).
const TEXTAREAS = new Set(["home_address", "allergies", "special_needs", "guardian_address"]);

export default function PostEntrancePage() {
  const canWrite = useHasPermission("school:admissions:write");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [appId, setAppId] = useState("");
  const [form, setForm] = useState<FormState>({ ...EMPTY });

  const { data, isLoading } = usePostEntranceForms({ status: statusFilter || undefined, page: 1, page_size: 100 });
  const { data: appsData } = useApplications({ page: 1, page_size: 200 });
  const { data: classData } = useClassOptions();
  const create = useCreatePostEntrance();
  const update = useUpdatePostEntrance();

  const rows: PostEntranceForm[] = data?.items || [];
  const apps: AdmissionApplication[] = appsData?.items || [];
  const classes = classData?.items || classData || [];

  const reset = () => { setForm({ ...EMPTY }); setEditId(null); setAppId(""); setShowForm(false); };

  const startCreate = () => { reset(); setShowForm(true); };

  const startEdit = (f: PostEntranceForm) => {
    setEditId(f.id);
    setAppId(f.application_id);
    setForm({
      ...EMPTY,
      ...Object.fromEntries(Object.keys(EMPTY).map((k) => [k, (f as any)[k] ?? ""])),
      status: f.status,
      applying_for_class_id: f.applying_for_class_id || "",
    } as FormState);
    setShowForm(true);
  };

  // Prefill candidate identity from the picked application (server prefills too).
  const onPickApp = (id: string) => {
    setAppId(id);
    const a = apps.find((x) => x.id === id);
    if (a) {
      setForm((prev) => ({
        ...prev,
        full_name: prev.full_name || `${a.first_name} ${a.last_name}`.trim(),
        date_of_birth: prev.date_of_birth || (a.date_of_birth || ""),
        gender: prev.gender || (a.gender || ""),
        applying_for_class_id: prev.applying_for_class_id || (a.applying_for_class_id || ""),
        applying_for_level: prev.applying_for_level || (a.applying_for_level || ""),
      }));
    }
  };

  const submit = () => {
    // Empty strings → omitted so the server keeps prefill/existing values.
    const payload: Record<string, unknown> = {};
    (Object.keys(form) as (keyof FormState)[]).forEach((k) => {
      const v = form[k];
      if (v !== "") payload[k] = v;
    });
    if (editId) {
      update.mutate({ id: editId, data: payload }, { onSuccess: reset });
    } else {
      create.mutate({ ...payload, application_id: appId }, { onSuccess: reset });
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/admissions" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Admissions</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Admissions</span><span>/</span><span className="text-brand-600 font-semibold">Post Entrance Form</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Post Entrance Form</h1>
          <p className="text-slate-500 text-sm mt-0.5">Full candidate registration after the entrance exam.</p>
        </div>
        {canWrite && !showForm && <button onClick={startCreate} className="btn-primary gap-2"><Plus size={15} /> New Form</button>}
      </div>

      <div className="mb-5 flex bg-slate-100 rounded-lg p-0.5 w-fit">
        {[["", "All"], ...STATUSES.map((s) => [s, s[0].toUpperCase() + s.slice(1)])].map(([val, label]) => (
          <button key={val || "all"} onClick={() => setStatusFilter(val)}
            className={cn("px-3 py-1.5 text-xs font-semibold rounded-md capitalize transition-colors", statusFilter === val ? "bg-white shadow text-slate-900" : "text-slate-500 hover:text-slate-700")}>
            {label}
          </button>
        ))}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editId ? "Edit post-entrance form" : "New post-entrance form"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>

          {/* Application picker (fixed once created) */}
          <div className="mb-5 max-w-md">
            <label className="label">Application *</label>
            <select value={appId} onChange={(e) => onPickApp(e.target.value)} disabled={!!editId} className="input">
              <option value="">— Select applicant —</option>
              {apps.map((a) => <option key={a.id} value={a.id}>{a.full_name} · {a.status}</option>)}
            </select>
          </div>

          <div className="space-y-6">
            {SECTIONS.map((section) => (
              <div key={section.title}>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">{section.title}</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {section.fields.map(([key, label]) => (
                    <div key={key} className={cn(TEXTAREAS.has(key) && "md:col-span-3")}>
                      <label className="label">{label}</label>
                      {TEXTAREAS.has(key) ? (
                        <textarea value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="input" rows={2} />
                      ) : (
                        <input type={key === "date_of_birth" ? "date" : "text"} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="input" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Class + status */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="label">Applying for class</label>
                <select value={form.applying_for_class_id} onChange={(e) => setForm({ ...form, applying_for_class_id: e.target.value })} className="input">
                  <option value="">—</option>
                  {classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
                  {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={(!editId && !appId) || create.isPending || update.isPending} className="btn-primary gap-2">
              {(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />} {editId ? "Save" : "Create"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><FileText size={30} className="mx-auto mb-2 opacity-50" />No post-entrance forms yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">
              {["Candidate", "Class", "Status", "Submitted", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((f) => (
                <tr key={f.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{f.candidate_name || f.full_name || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{f.applying_for_class_name || f.applying_for_level || "—"}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[f.status])}>{f.status}</span></td>
                  <td className="px-5 py-4 text-xs text-slate-500">{f.submitted_at ? formatDate(f.submitted_at) : "—"}</td>
                  <td className="px-5 py-4 text-right">
                    {canWrite && <button onClick={() => startEdit(f)} className="text-xs font-semibold text-brand-600 hover:underline">Edit</button>}
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
