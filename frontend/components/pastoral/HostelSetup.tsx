"use client";

import { useState } from "react";
import {
  useHostels,
  useHostelManagers, useAddHostelManager, useRemoveHostelManager,
  useHostelLifeGrades, useCreateHostelLifeGrade, useUpdateHostelLifeGrade, useDeleteHostelLifeGrade,
  useHostelCommentBank, useCreateHostelComment, useUpdateHostelComment, useDeleteHostelComment,
} from "@/hooks/usePastoral";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Power, UserPlus } from "lucide-react";

type Sub = "managers" | "grades" | "comments";
const SUBS: [Sub, string][] = [["managers", "Managers"], ["grades", "Life Grades"], ["comments", "Comment Bank"]];

export function HostelSetup({ canWrite }: { canWrite: boolean }) {
  const [sub, setSub] = useState<Sub>("managers");
  return (
    <div>
      <div className="inline-flex gap-1 bg-slate-100 rounded-lg p-1 mb-5">
        {SUBS.map(([k, l]) => (
          <button key={k} onClick={() => setSub(k)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-md transition", sub === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {sub === "managers" ? <Managers canWrite={canWrite} /> : sub === "grades" ? <Grades canWrite={canWrite} /> : <Comments canWrite={canWrite} />}
    </div>
  );
}

function Managers({ canWrite }: { canWrite: boolean }) {
  const { data: hostelData } = useHostels();
  const hostels = hostelData?.items ?? [];
  const [hostelId, setHostelId] = useState("");
  const [userId, setUserId] = useState<string | null>(null);
  const { data: managers = [], isLoading } = useHostelManagers(hostelId);
  const add = useAddHostelManager();
  const remove = useRemoveHostelManager();

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <label className="label">Hostel</label>
        <select value={hostelId} onChange={(e) => setHostelId(e.target.value)} className="input max-w-sm">
          <option value="">— Select a hostel —</option>
          {(hostels as any[]).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
        {hostelId && canWrite && (
          <div className="flex flex-wrap items-end gap-3 mt-4 pt-4 border-t border-slate-100">
            <div className="flex-1 min-w-[200px]"><label className="label">Add staff as manager</label><EntityPicker type="staff" value={userId} onChange={setUserId} /></div>
            <button onClick={() => userId && add.mutate({ hostel_id: hostelId, user_id: userId }, { onSuccess: () => setUserId(null) })} disabled={!userId || add.isPending} className="btn-primary gap-2"><UserPlus size={15} /> Add Manager</button>
          </div>
        )}
      </div>

      {!hostelId ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">Select a hostel to manage its managers.</p>
      ) : isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (managers as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No managers assigned.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(managers as any[]).map((m) => (
            <div key={m.id} className="flex items-center justify-between px-5 py-3">
              <span className="text-sm font-semibold text-slate-800">{m.user_name || m.user_id.slice(0, 8)}</span>
              {canWrite && <button onClick={() => remove.mutate(m.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Grades({ canWrite }: { canWrite: boolean }) {
  const { data: grades = [], isLoading } = useHostelLifeGrades();
  const create = useCreateHostelLifeGrade();
  const update = useUpdateHostelLifeGrade();
  const del = useDeleteHostelLifeGrade();
  const [f, setF] = useState({ name: "", sort_order: "", description: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Grade name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Excellent" /></div>
          <div><label className="label">Order</label><input type="number" value={f.sort_order} onChange={(e) => setF({ ...f, sort_order: e.target.value })} className="input w-20" /></div>
          <div className="flex-1 min-w-[160px]"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), sort_order: f.sort_order ? Number(f.sort_order) : 0, description: f.description || null }, { onSuccess: () => setF({ name: "", sort_order: "", description: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Grade</button>
        </div>
      )}
      {isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (grades as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No grades configured.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(grades as any[]).map((g) => (
            <div key={g.id} className="flex items-center justify-between px-5 py-3 gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-800">{g.name} <span className="text-xs font-normal text-slate-400">· #{g.sort_order}</span></p>
                {g.description && <p className="text-xs text-slate-400 truncate">{g.description}</p>}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={cn("badge", g.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{g.is_active ? "Active" : "Inactive"}</span>
                {canWrite && <>
                  <button onClick={() => update.mutate({ id: g.id, data: { is_active: !g.is_active } })} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                  <button onClick={() => { if (confirm(`Delete ${g.name}?`)) del.mutate(g.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                </>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Comments({ canWrite }: { canWrite: boolean }) {
  const { data: comments = [], isLoading } = useHostelCommentBank();
  const create = useCreateHostelComment();
  const update = useUpdateHostelComment();
  const del = useDeleteHostelComment();
  const [f, setF] = useState({ text: "", category: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px]"><label className="label">Comment</label><input value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} className="input" placeholder="e.g. Keeps a tidy bed space." /></div>
          <div><label className="label">Category</label><input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="input w-36" placeholder="Neatness" /></div>
          <button onClick={() => f.text.trim() && create.mutate({ text: f.text.trim(), category: f.category || null }, { onSuccess: () => setF({ text: "", category: "" }) })} disabled={!f.text.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Comment</button>
        </div>
      )}
      {isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (comments as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No comments in the bank.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(comments as any[]).map((c) => (
            <div key={c.id} className="flex items-center justify-between px-5 py-3 gap-3">
              <div className="min-w-0">
                <p className="text-sm text-slate-800">{c.text}</p>
                {c.category && <p className="text-xs text-slate-400">{c.category}</p>}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={cn("badge", c.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{c.is_active ? "Active" : "Inactive"}</span>
                {canWrite && <>
                  <button onClick={() => update.mutate({ id: c.id, data: { is_active: !c.is_active } })} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                  <button onClick={() => { if (confirm("Delete this comment?")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                </>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
