"use client";

import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useTeachers, useCreateTeacher, useUpdateTeacher, useDeleteTeacher,
  useTeacherSubjects, useSetTeacherSubjects,
} from "@/hooks/useSchool";
import { useSections } from "@/hooks/usePlatform";
import { useSubjectOptions } from "@/hooks/useAcademics";
import { schoolApi, uploadApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, getInitials, resolveMediaUrl } from "@/lib/utils";
import { toast } from "sonner";
import {
  Search, Download, Plus, Eye, Pencil, Power, Trash2, BookOpen, X, Loader2, Camera, Check,
} from "lucide-react";
import type { Teacher, SchoolSection } from "@/types";

export default function ViewTeachersPage() {
  const canWrite = useHasPermission("settings:write");
  const [sectionId, setSectionId] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { data: sections } = useSections();
  const { data, isLoading } = useTeachers({ page, page_size: pageSize, search: search || undefined, section: sectionId || undefined });
  const teachers: Teacher[] = data?.items ?? [];

  const del = useDeleteTeacher();
  const update = useUpdateTeacher();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Teacher | null>(null);
  const [details, setDetails] = useState<Teacher | null>(null);
  const [subjectsFor, setSubjectsFor] = useState<Teacher | null>(null);

  const sectionLabel = sectionId ? (sections?.find((s) => s.id === sectionId)?.name ?? "SCHOOL") : "ALL SCHOOLS";

  const download = async () => {
    try {
      const blob = await schoolApi.teachers.exportCsv(sectionId || undefined);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "teachers.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Export failed."); }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Teachers</span><span>/</span><span className="text-brand-600 font-semibold">View Teachers</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-5">View Teachers</h1>

      {/* Select School */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-semibold text-slate-600">Select School</label>
          <select value={sectionId} onChange={(e) => { setSectionId(e.target.value); setPage(1); }} className="input w-auto min-w-[220px]">
            <option value="">All Schools</option>
            {(sections ?? []).map((s: SchoolSection) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-slate-100 bg-slate-50/60">
          <h2 className="text-sm font-bold text-slate-800">Teacher&apos;s Information For <span className="uppercase">{sectionLabel}</span></h2>
          <div className="flex items-center gap-2">
            <button onClick={download} className="btn-secondary gap-1.5 py-1.5"><Download size={14} /> Download Teachers List</button>
            {canWrite && <button onClick={() => { setEditing(null); setFormOpen(true); }} className="btn-primary gap-1.5 py-1.5"><Plus size={14} /> Add a Teacher</button>}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
          <label className="text-xs text-slate-500 flex items-center gap-2">
            <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} className="input w-auto py-1 text-sm">
              {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            records
          </label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search…" className="input pl-9 py-1.5 text-sm" />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-y border-slate-100">
              {["Photo", "First Name", "Last Name", "Other Names", "Employee ID", "E-mail", "Phone", "Status", "Actions"].map((h) => (
                <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                <tr><td colSpan={9} className="py-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
              ) : teachers.length === 0 ? (
                <tr><td colSpan={9} className="py-12 text-center text-sm text-slate-400">No teachers{sectionId ? " in this school" : ""} yet.</td></tr>
              ) : teachers.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3"><PhotoCell teacher={t} canWrite={canWrite} /></td>
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{t.first_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{t.last_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{t.other_names || "—"}</td>
                  <td className="px-4 py-3 text-sm font-mono text-slate-600">{t.employee_id || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{t.email}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{t.phone || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={cn("badge", t.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{t.is_active ? "Active" : "Inactive"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      <ActBtn onClick={() => setDetails(t)} icon={Eye} label="Details" tone="brand" />
                      {canWrite && <>
                        <ActBtn onClick={() => { setEditing(t); setFormOpen(true); }} icon={Pencil} label="Edit" tone="slate" />
                        <ActBtn onClick={() => update.mutate({ id: t.id, data: { is_active: !t.is_active } })} icon={Power} label={t.is_active ? "Deactivate" : "Activate"} tone={t.is_active ? "amber" : "emerald"} />
                        <ActBtn onClick={() => { if (confirm(`Remove ${t.first_name} ${t.last_name}?`)) del.mutate(t.id); }} icon={Trash2} label="Delete" tone="red" />
                        <ActBtn onClick={() => setSubjectsFor(t)} icon={BookOpen} label="Subjects" tone="violet" />
                      </>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 text-xs text-slate-500">
            <span>Page {data.page} of {data.total_pages} · {data.total} teachers</span>
            <div className="flex gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary py-1 px-2 disabled:opacity-40">Prev</button>
              <button onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))} disabled={page >= data.total_pages} className="btn-secondary py-1 px-2 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {formOpen && <TeacherForm teacher={editing} sections={sections ?? []} onClose={() => setFormOpen(false)} />}
      {details && <DetailsModal teacher={details} onClose={() => setDetails(null)} />}
      {subjectsFor && <SubjectsModal teacher={subjectsFor} onClose={() => setSubjectsFor(null)} />}
    </div>
  );
}

function ActBtn({ onClick, icon: Icon, label, tone }: { onClick: () => void; icon: any; label: string; tone: string }) {
  const tones: Record<string, string> = {
    brand: "text-brand-600 hover:bg-brand-50", slate: "text-slate-600 hover:bg-slate-100",
    amber: "text-amber-600 hover:bg-amber-50", emerald: "text-emerald-600 hover:bg-emerald-50",
    red: "text-red-500 hover:bg-red-50", violet: "text-violet-600 hover:bg-violet-50",
  };
  return (
    <button onClick={onClick} className={cn("inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-md transition", tones[tone])}>
      <Icon size={12} /> {label}
    </button>
  );
}

function PhotoCell({ teacher, canWrite }: { teacher: Teacher; canWrite: boolean }) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const setPhoto = useMutation({
    mutationFn: (file: File) => uploadApi.avatarForUser(teacher.id, file),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teachers"] }); toast.success("Photo updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Photo upload failed."),
  });
  return (
    <div className="relative w-11 h-11 shrink-0 group/av">
      {teacher.photo_url ? (
        <img src={resolveMediaUrl(teacher.photo_url)} alt="" className="w-11 h-11 rounded-full object-cover bg-slate-100" />
      ) : (
        <div className="w-11 h-11 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center text-sm font-bold">{getInitials(`${teacher.first_name} ${teacher.last_name}`)}</div>
      )}
      {canWrite && (
        <>
          <button onClick={() => inputRef.current?.click()} disabled={setPhoto.isPending} title="Set photo"
            className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-slate-700 text-white flex items-center justify-center shadow ring-2 ring-white opacity-0 group-hover/av:opacity-100 transition disabled:opacity-100">
            {setPhoto.isPending ? <Loader2 size={10} className="animate-spin" /> : <Camera size={10} />}
          </button>
          <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) setPhoto.mutate(f); e.target.value = ""; }} />
        </>
      )}
    </div>
  );
}

function TeacherForm({ teacher, sections, onClose }: { teacher: Teacher | null; sections: SchoolSection[]; onClose: () => void }) {
  const create = useCreateTeacher();
  const update = useUpdateTeacher();
  const [f, setF] = useState({
    first_name: teacher?.first_name ?? "", last_name: teacher?.last_name ?? "", other_names: teacher?.other_names ?? "",
    employee_id: teacher?.employee_id ?? "", email: teacher?.email ?? "", phone: teacher?.phone ?? "",
    department: teacher?.department ?? "", qualification: teacher?.qualification ?? "", hire_date: teacher?.hire_date ?? "",
    section_id: teacher?.section_id ?? "",
  });
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));
  const busy = create.isPending || update.isPending;

  const submit = () => {
    if (!f.first_name.trim() || !f.last_name.trim() || !f.email.trim()) { toast.error("First name, last name and email are required."); return; }
    const payload: any = { ...f, section_id: f.section_id || null };
    if (teacher) update.mutate({ id: teacher.id, data: payload }, { onSuccess: onClose });
    else create.mutate(payload, { onSuccess: onClose });
  };

  return (
    <Modal title={teacher ? "Edit Teacher" : "Add a Teacher"} onClose={onClose} wide>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="First Name *"><input value={f.first_name} onChange={(e) => set("first_name", e.target.value)} className="input" /></Field>
        <Field label="Last Name *"><input value={f.last_name} onChange={(e) => set("last_name", e.target.value)} className="input" /></Field>
        <Field label="Other Names"><input value={f.other_names} onChange={(e) => set("other_names", e.target.value)} className="input" /></Field>
        <Field label="Employee ID"><input value={f.employee_id} onChange={(e) => set("employee_id", e.target.value)} className="input" /></Field>
        <Field label="E-mail *"><input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} className="input" /></Field>
        <Field label="Phone"><input value={f.phone} onChange={(e) => set("phone", e.target.value)} className="input" /></Field>
        <Field label="Department"><input value={f.department} onChange={(e) => set("department", e.target.value)} className="input" /></Field>
        <Field label="Qualification"><input value={f.qualification} onChange={(e) => set("qualification", e.target.value)} className="input" /></Field>
        <Field label="Hire Date"><input type="date" value={f.hire_date ?? ""} onChange={(e) => set("hire_date", e.target.value)} className="input" /></Field>
        <Field label="School (Section)">
          <select value={f.section_id} onChange={(e) => set("section_id", e.target.value)} className="input">
            <option value="">— Unassigned —</option>
            {sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </Field>
      </div>
      <div className="flex justify-end gap-2 pt-4">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={submit} disabled={busy} className="btn-primary gap-2">{busy && <Loader2 size={15} className="animate-spin" />}{teacher ? "Save" : "Add Teacher"}</button>
      </div>
    </Modal>
  );
}

function DetailsModal({ teacher, onClose }: { teacher: Teacher; onClose: () => void }) {
  const rows: [string, string][] = [
    ["First Name", teacher.first_name], ["Last Name", teacher.last_name], ["Other Names", teacher.other_names || "—"],
    ["Employee ID", teacher.employee_id || "—"], ["E-mail", teacher.email], ["Phone", teacher.phone || "—"],
    ["Department", teacher.department || "—"], ["Qualification", teacher.qualification || "—"],
    ["School", teacher.section_name || "—"], ["Hire Date", teacher.hire_date || "—"],
    ["Status", teacher.is_active ? "Active" : "Inactive"],
  ];
  return (
    <Modal title="Teacher Details" onClose={onClose}>
      <div className="flex items-center gap-3 mb-4">
        {teacher.photo_url ? <img src={resolveMediaUrl(teacher.photo_url)} alt="" className="w-14 h-14 rounded-full object-cover" />
          : <div className="w-14 h-14 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center font-bold">{getInitials(`${teacher.first_name} ${teacher.last_name}`)}</div>}
        <div><p className="font-bold text-slate-800">{teacher.first_name} {teacher.last_name}</p><p className="text-xs text-slate-400">{teacher.email}</p></div>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {rows.map(([k, v]) => <div key={k}><dt className="text-[10px] font-bold uppercase text-slate-400">{k}</dt><dd className="text-sm text-slate-800">{v}</dd></div>)}
      </dl>
      {(teacher.subjects?.length ?? 0) > 0 && (
        <div className="mt-3"><dt className="text-[10px] font-bold uppercase text-slate-400 mb-1">Subject Labels</dt>
          <div className="flex flex-wrap gap-1">{teacher.subjects.map((s) => <span key={s} className="badge bg-brand-50 text-brand-700 border-brand-200">{s}</span>)}</div></div>
      )}
    </Modal>
  );
}

function SubjectsModal({ teacher, onClose }: { teacher: Teacher; onClose: () => void }) {
  const { data: current, isLoading } = useTeacherSubjects(teacher.id);
  const { data: allResp } = useSubjectOptions();
  const save = useSetTeacherSubjects();
  const allSubjects: { id: string; name: string; code?: string | null }[] = allResp?.items ?? [];
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const selected = picked ?? new Set<string>((current?.items ?? []).map((s: any) => s.id));

  const toggle = (id: string) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setPicked(next);
  };

  return (
    <Modal title={`Subjects · ${teacher.first_name} ${teacher.last_name}`} onClose={onClose}>
      <p className="text-xs text-slate-500 mb-3">Select the subjects this teacher teaches. A subject has one teacher — assigning it here reassigns it from any previous teacher.</p>
      {isLoading ? <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
        : allSubjects.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center">No subjects defined yet.</p>
        : (
          <div className="max-h-72 overflow-y-auto space-y-1">
            {allSubjects.map((s) => {
              const on = selected.has(s.id);
              return (
                <button key={s.id} onClick={() => toggle(s.id)} className={cn("w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition", on ? "bg-violet-50" : "hover:bg-slate-50")}>
                  <span className={cn("w-4 h-4 rounded border flex items-center justify-center shrink-0", on ? "bg-violet-600 border-violet-600" : "border-slate-300")}>{on && <Check size={12} className="text-white" />}</span>
                  <span className="text-sm text-slate-700 flex-1">{s.name}</span>
                  {s.code && <span className="text-xs text-slate-400 font-mono">{s.code}</span>}
                </button>
              );
            })}
          </div>
        )}
      <div className="flex justify-end gap-2 pt-4">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={() => save.mutate({ id: teacher.id, subjectIds: [...selected] }, { onSuccess: onClose })} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button>
      </div>
    </Modal>
  );
}

function Modal({ title, children, onClose, wide }: { title: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className={cn("bg-white rounded-xl border border-slate-200 shadow-xl w-full max-h-[85vh] overflow-y-auto", wide ? "max-w-2xl" : "max-w-md")} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 sticky top-0 bg-white">
          <h3 className="text-sm font-bold text-slate-800">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="label">{label}</label>{children}</div>;
}
