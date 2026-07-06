"use client";

import { useState } from "react";
import {
  useParentLinks, useCreateParentLink, useUpdateParentLink, useDeleteParentLink,
} from "@/hooks/usePeople";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import {
  Contact, Plus, X, Loader2, Trash2, Star, Search, AlertTriangle,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { ParentLink } from "@/types";

const RELATIONSHIPS = ["parent", "guardian", "other"];

export default function ParentsDirectoryPage() {
  const canWrite = useHasPermission("school:parents:write");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading, isError, refetch } = useParentLinks(
    search.trim() ? { search: search.trim() } : undefined,
  );
  const createLink = useCreateParentLink();
  const updateLink = useUpdateParentLink();
  const deleteLink = useDeleteParentLink();

  const [form, setForm] = useState({
    user_id: "", student_id: "", relationship_type: "parent", is_primary: false,
  });
  const resetForm = () => {
    setForm({ user_id: "", student_id: "", relationship_type: "parent", is_primary: false });
    setShowForm(false);
  };
  const handleCreate = () => {
    createLink.mutate(
      {
        user_id: form.user_id.trim(),
        student_id: form.student_id.trim(),
        relationship_type: form.relationship_type,
        is_primary: form.is_primary,
      },
      { onSuccess: resetForm },
    );
  };

  const links = data?.items;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>People &amp; HR</span><span>/</span>
            <span className="text-brand-600 font-semibold">Parents Directory</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Parents Directory</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Guardians and the students they’re linked to.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => setShowForm((s) => !s)} className="btn-primary gap-2">
            <Plus size={15} /> Link Guardian
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative mb-5 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search parent or student…"
          className="input pl-9"
        />
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">Link a Guardian to a Student</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Parent / Guardian *</label>
              <EntityPicker
                type="parent"
                value={form.user_id || null}
                onChange={(id) => setForm({ ...form, user_id: id || "" })}
              />
            </div>
            <div>
              <label className="label">Student *</label>
              <EntityPicker
                type="student"
                value={form.student_id || null}
                onChange={(id) => setForm({ ...form, student_id: id || "" })}
              />
            </div>
            <div>
              <label className="label">Relationship</label>
              <select value={form.relationship_type} onChange={(e) => setForm({ ...form, relationship_type: e.target.value })} className="input capitalize">
                {RELATIONSHIPS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2 mt-6">
              <input id="primary" type="checkbox" checked={form.is_primary} onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />
              <label htmlFor="primary" className="text-xs font-medium text-slate-700">Primary contact (receives report cards / SMS)</label>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleCreate} disabled={!form.user_id.trim() || !form.student_id.trim() || createLink.isPending} className="btn-primary gap-2">
              {createLink.isPending && <Loader2 size={15} className="animate-spin" />}
              Link
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Parent / Guardian", "Student", "Relationship", "Primary", "Linked", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                  <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-24" /></td>
                ))}</tr>
              ))
            ) : isError ? (
              <tr>
                <td colSpan={6} className="py-14 text-center">
                  <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
                  <p className="text-sm font-semibold text-slate-600">Couldn’t load the directory.</p>
                  <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
                </td>
              </tr>
            ) : links && links.length > 0 ? (
              links.map((link) => (
                <ParentRow
                  key={link.id}
                  link={link}
                  canWrite={canWrite}
                  onUpdate={(data) => updateLink.mutate({ id: link.id, data })}
                  onDelete={() => { if (confirm("Unlink this guardian from the student?")) deleteLink.mutate(link.id); }}
                />
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-16 text-center text-slate-400">
                  <Contact size={36} className="mx-auto mb-3 opacity-40" />
                  <p className="font-semibold">No guardian links yet</p>
                  {canWrite && <p className="text-sm mt-1">Use “Link Guardian” to connect a parent account to a student.</p>}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ParentRow({
  link, canWrite, onUpdate, onDelete,
}: {
  link: ParentLink;
  canWrite: boolean;
  onUpdate: (data: { relationship_type?: string; is_primary?: boolean }) => void;
  onDelete: () => void;
}) {
  return (
    <tr className="hover:bg-slate-50/70">
      <td className="px-5 py-4">
        <p className="text-sm font-semibold text-slate-800">{link.parent.full_name}</p>
        <p className="text-xs text-slate-500">{link.parent.email || link.parent.phone || "—"}</p>
      </td>
      <td className="px-5 py-4">
        <p className="text-sm text-slate-700">{link.student.full_name}</p>
        <p className="text-xs text-slate-400">
          {link.student.student_id}{link.student.class_name ? ` · ${link.student.class_name}` : ""}
        </p>
      </td>
      <td className="px-5 py-4">
        {canWrite ? (
          <select
            value={link.relationship_type}
            onChange={(e) => onUpdate({ relationship_type: e.target.value })}
            className="input py-1 text-xs capitalize w-32"
          >
            {RELATIONSHIPS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        ) : (
          <span className="text-sm text-slate-600 capitalize">{link.relationship_type}</span>
        )}
      </td>
      <td className="px-5 py-4">
        <button
          onClick={() => canWrite && onUpdate({ is_primary: !link.is_primary })}
          disabled={!canWrite}
          title={link.is_primary ? "Primary contact" : "Set as primary"}
          className={link.is_primary ? "text-amber-500" : "text-slate-300 hover:text-amber-400"}
        >
          <Star size={16} fill={link.is_primary ? "currentColor" : "none"} />
        </button>
      </td>
      <td className="px-5 py-4"><span className="text-xs text-slate-500">{formatDate(link.created_at)}</span></td>
      <td className="px-5 py-4">
        {canWrite && (
          <button onClick={onDelete} className="text-slate-400 hover:text-red-600 p-1" title="Unlink">
            <Trash2 size={14} />
          </button>
        )}
      </td>
    </tr>
  );
}
