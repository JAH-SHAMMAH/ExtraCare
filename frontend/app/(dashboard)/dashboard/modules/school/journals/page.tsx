"use client";

import { useState } from "react";
import {
  useJournals,
  useCreateJournal,
  useDeleteJournal,
} from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { formatDate } from "@/lib/utils";
import { Camera, Plus, X, Loader2, Trash2, Tag, Image as ImageIcon } from "lucide-react";
import type { PhotoJournal } from "@/types";

export default function JournalsPage() {
  const canWrite = useHasPermission("school:write");
  const [showForm, setShowForm] = useState(false);
  const [tagFilter, setTagFilter] = useState("");

  const { data, isLoading } = useJournals({
    tag: tagFilter || undefined,
    page: 1,
    page_size: 50,
  });
  const createJournal = useCreateJournal();
  const deleteJournal = useDeleteJournal();

  const [form, setForm] = useState({
    title: "",
    description: "",
    photo_url: "",
    taken_date: new Date().toISOString().substring(0, 10),
    class_id: "",
    club_id: "",
    tags: "",
  });

  const resetForm = () => {
    setForm({
      title: "", description: "", photo_url: "",
      taken_date: new Date().toISOString().substring(0, 10),
      class_id: "", club_id: "", tags: "",
    });
    setShowForm(false);
  };

  const handleSubmit = () => {
    createJournal.mutate(
      {
        title: form.title,
        description: form.description || null,
        photo_url: form.photo_url,
        taken_date: form.taken_date || null,
        class_id: form.class_id || null,
        club_id: form.club_id || null,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
      },
      { onSuccess: resetForm },
    );
  };

  const journals = data?.items as PhotoJournal[] | undefined;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Photo Journals</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Photo Journals</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Capture school events, class moments, and club activities in photos.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => setShowForm(true)} className="btn-primary gap-2">
            <Plus size={15} />
            Post Journal
          </button>
        )}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Photo Journal</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Title *</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Photo URL *</label>
              <input value={form.photo_url} onChange={(e) => setForm({ ...form, photo_url: e.target.value })} className="input" placeholder="https://..." />
            </div>
            <div>
              <label className="label">Class ID</label>
              <input value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Club ID</label>
              <input value={form.club_id} onChange={(e) => setForm({ ...form, club_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Taken On</label>
              <input type="date" value={form.taken_date} onChange={(e) => setForm({ ...form, taken_date: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Tags (comma separated)</label>
              <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} className="input" placeholder="sports, awards" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button
              onClick={handleSubmit}
              disabled={createJournal.isPending || !form.title || !form.photo_url}
              className="btn-primary gap-2"
            >
              {createJournal.isPending && <Loader2 size={15} className="animate-spin" />}
              Post
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex items-center gap-3">
        <div className="flex items-center gap-2 flex-1">
          <Tag size={14} className="text-slate-400" />
          <input
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            placeholder="Filter by tag (e.g. sports)"
            className="input flex-1"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-64 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : journals && journals.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {journals.map((j) => (
            <div key={j.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
              <div className="relative h-48 bg-slate-100">
                {j.photo_url ? (
                  <img src={j.photo_url} alt={j.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <ImageIcon size={32} className="text-slate-300" />
                  </div>
                )}
                {canWrite && (
                  <button
                    onClick={() => { if (confirm("Delete this journal?")) deleteJournal.mutate(j.id); }}
                    className="absolute top-2 right-2 bg-white/90 hover:bg-white rounded-lg p-1.5 text-red-500 shadow"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
              <div className="p-4">
                <h3 className="text-sm font-bold text-slate-900 mb-1">{j.title}</h3>
                {j.description && <p className="text-xs text-slate-500 line-clamp-2 mb-2">{j.description}</p>}
                <div className="flex items-center justify-between mt-3">
                  <span className="text-[10px] text-slate-400">
                    {formatDate(j.taken_date || j.created_at)}
                  </span>
                </div>
                {j.tags && j.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {j.tags.map((t) => (
                      <span key={t} className="text-[10px] px-2 py-0.5 bg-slate-100 rounded-full text-slate-600">#{t}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <Camera size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No photo journals yet</p>
        </div>
      )}
    </div>
  );
}
