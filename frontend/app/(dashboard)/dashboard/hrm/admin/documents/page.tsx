"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useHrDocuments, useCreateHrDocument, useDeleteHrDocument, type HrDocument } from "@/hooks/useHrDocuments";
import { uploadApi } from "@/lib/api";
import { resolveMediaUrl, cn } from "@/lib/utils";
import { FileText, Upload, Loader2, Trash2, Download, AlertTriangle, Paperclip } from "lucide-react";

export default function HrDocumentsPage() {
  const { data, isLoading, isError, refetch } = useHrDocuments();
  const create = useCreateHrDocument();
  const del = useDeleteHrDocument();
  const [file, setFile] = useState<File | null>(null);
  const [f, setF] = useState({ title: "", category: "", description: "" });
  const [uploading, setUploading] = useState(false);
  const reset = () => { setFile(null); setF({ title: "", category: "", description: "" }); };
  const rows = data ?? [];

  const submit = async () => {
    if (!file || !f.title.trim()) return;
    setUploading(true);
    try {
      const res = await uploadApi.document(file, f.category || undefined);
      create.mutate(
        { title: f.title.trim(), category: f.category || null, description: f.description || null, file_url: res.url, filename: res.filename },
        { onSuccess: reset },
      );
    } catch {
      toast.error("Upload failed — check the file type and size (max 15 MB).");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/admin" className="hover:text-brand-600">Admin</Link><span>/</span><span className="text-brand-600 font-semibold">Documents</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Documents &amp; Templates</h1>
        <p className="text-slate-500 text-sm mt-0.5">HR policies, forms and templates — upload once, available to your team.</p>
      </div>

      {/* Upload */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Staff Handbook" /></div>
          <div><label className="label">Category</label><input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="input" placeholder="e.g. Policy, Template" /></div>
          <div className="md:col-span-2"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" placeholder="Optional" /></div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 cursor-pointer hover:text-brand-600">
            <Paperclip size={15} /> {file ? file.name : "Choose file…"}
            <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,image/*" />
          </label>
          <button onClick={submit} disabled={!file || !f.title.trim() || uploading || create.isPending} className="btn-primary gap-2">
            {(uploading || create.isPending) ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} Upload
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load documents.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><FileText size={34} className="mb-3 opacity-40" /><p className="font-semibold">No documents yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((d: HrDocument) => (
            <div key={d.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center shrink-0"><FileText size={16} /></div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-800 truncate">{d.title}</p>
                  {d.category && <span className="badge bg-slate-100 text-slate-500 border-slate-200">{d.category}</span>}
                </div>
                <p className="text-xs text-slate-400 truncate">{d.description || d.filename || "—"}</p>
              </div>
              <a href={resolveMediaUrl(d.file_url)} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-brand-600 p-1.5" title="Download / view"><Download size={15} /></a>
              <button onClick={() => { if (confirm(`Remove “${d.title}”?`)) del.mutate(d.id); }} className="text-slate-400 hover:text-red-600 p-1.5" title="Remove"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
