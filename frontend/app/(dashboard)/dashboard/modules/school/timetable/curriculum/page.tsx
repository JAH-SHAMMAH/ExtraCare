"use client";

import { useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { useClasses, useSubjects } from "@/hooks/useSchool";
import { useCurriculum, useCreateCurriculum, useDeleteCurriculum } from "@/hooks/useTimetableModule";
import { useUploadDocument } from "@/hooks/useUpload";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { BookMarked, Plus, X, Loader2, Trash2, FileText, Upload } from "lucide-react";
import type { Curriculum } from "@/types";

export default function ManageCurriculumPage() {
  const canWrite = useHasPermission("school:timetable:write");
  const { data: sessions } = useSessions();
  const { data: classesData } = useClasses({ page_size: 200 });
  const { data: subjectsData } = useSubjects({ page_size: 200 });
  const sessionNames = useMemo(() => Array.from(new Set((sessions ?? []).map((s: any) => s.name))), [sessions]);

  const [session, setSession] = useState("");
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const classes = classesData?.items ?? [];
  const subjects = subjectsData?.items ?? [];

  const { data, isLoading } = useCurriculum({ class_id: classId || undefined, subject_id: subjectId || undefined, academic_year: session || undefined });
  const create = useCreateCurriculum();
  const del = useDeleteCurriculum();
  const upload = useUploadDocument();
  const items: Curriculum[] = data?.items ?? [];

  const [show, setShow] = useState(false);
  const [form, setForm] = useState<{ name: string; class_id: string; subject_id: string; file_url: string }>({ name: "", class_id: "", subject_id: "", file_url: "" });

  const onFile = async (file?: File) => {
    if (!file) return;
    const res: any = await upload.mutateAsync({ file, category: "curriculum" });
    setForm((f) => ({ ...f, file_url: res?.url ?? res?.file_url ?? res }));
  };
  const submit = () => create.mutate({ name: form.name.trim(), class_id: form.class_id || null, subject_id: form.subject_id || null, file_url: form.file_url || null, academic_year: session || null },
    { onSuccess: () => { setShow(false); setForm({ name: "", class_id: "", subject_id: "", file_url: "" }); } });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">Manage Curriculum</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Curriculum</h1>
          <p className="text-slate-500 text-sm mt-0.5">Curriculum documents per class and subject.</p>
        </div>
        {canWrite && <button onClick={() => { setShow(true); setForm({ name: "", class_id: classId, subject_id: subjectId, file_url: "" }); }} className="btn-primary gap-2"><Plus size={15} /> New Curriculum</button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap gap-4 items-end">
        <div><label className="label">Session</label><select value={session} onChange={(e) => setSession(e.target.value)} className="input min-w-[140px]"><option value="">All</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><label className="label">Class</label><select value={classId} onChange={(e) => setClassId(e.target.value)} className="input min-w-[140px]"><option value="">All</option>{classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Subject</label><select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input min-w-[140px]"><option value="">All</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Name", "Subject", "File", "Action"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : items.length > 0 ? items.map((c, i) => (
              <tr key={c.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{c.name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{c.subject_name || "—"}</td>
                <td className="px-5 py-3 text-sm">{c.file_url ? <a href={c.file_url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline inline-flex items-center gap-1"><FileText size={13} /> View</a> : <span className="text-slate-300">—</span>}</td>
                <td className="px-5 py-3">{canWrite && <button onClick={() => { if (confirm("Delete curriculum?")) del.mutate(c.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>}</td>
              </tr>
            )) : <tr><td colSpan={5} className="py-16 text-center text-slate-400"><BookMarked size={30} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">No curriculum yet</p></td></tr>}
          </tbody>
        </table>
      </div>

      {show && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setShow(false)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">New Curriculum</h3><button onClick={() => setShow(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-4">
              <div><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Scheme of Work — Term 1" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Class</label><select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input"><option value="">—</option>{classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
                <div><label className="label">Subject</label><select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input"><option value="">—</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
              </div>
              <div>
                <label className="label">Document</label>
                <label className="btn-secondary gap-2 cursor-pointer inline-flex">{upload.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} {form.file_url ? "Replace file" : "Upload file"}<input type="file" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} /></label>
                {form.file_url && <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1"><FileText size={12} /> Attached</p>}
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setShow(false)} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
