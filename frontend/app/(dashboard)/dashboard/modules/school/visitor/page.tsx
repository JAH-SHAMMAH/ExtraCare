"use client";

import { useState } from "react";
import {
  useVisitors, useSignInVisitor, useSignOutVisitor, useDeleteVisitor,
  useCollections, useRecordCollection, useDeleteCollection,
} from "@/hooks/useOperations";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { UserCheck, Plus, X, Loader2, Trash2, AlertTriangle, ShieldAlert, LogOut, ShieldCheck } from "lucide-react";

type Tab = "visitors" | "collections";

export default function VisitorPage() {
  const canWrite = useHasPermission("school_admin:write");
  const [tab, setTab] = useState<Tab>("visitors");

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Operations</span><span>/</span><span className="text-brand-600 font-semibold">Visitor Management</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Visitor Management</h1>
        <p className="text-slate-500 text-sm mt-0.5">Front-desk sign-in and child collection — a safeguarding record.</p>
      </div>

      <div className="flex items-center gap-2 text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} />
        Safeguarding: every entry is audit-logged, records can’t be silently deleted, and a child collection records who authorised the pickup.
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["visitors", "Visitors"], ["collections", "Child Collection"]] as [Tab, string][]).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{label}</button>
        ))}
      </div>

      {tab === "visitors" ? <VisitorsTab canWrite={canWrite} /> : <CollectionsTab canWrite={canWrite} />}
    </div>
  );
}

function VisitorsTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useVisitors();
  const signIn = useSignInVisitor();
  const signOut = useSignOutVisitor();
  const del = useDeleteVisitor();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ visitor_name: "", organization: "", purpose: "", host_name: "", phone: "", badge_no: "" });

  const reset = () => { setForm({ visitor_name: "", organization: "", purpose: "", host_name: "", phone: "", badge_no: "" }); setShow(false); };
  const submit = () => signIn.mutate({ ...form, organization: form.organization || null, purpose: form.purpose || null, host_name: form.host_name || null, phone: form.phone || null, badge_no: form.badge_no || null }, { onSuccess: reset });

  const rows = data?.items;

  return (
    <>
      <div className="flex justify-end mb-4">{canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Sign In Visitor</button>}</div>
      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Sign In Visitor</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Visitor Name *</label><input value={form.visitor_name} onChange={(e) => setForm({ ...form, visitor_name: e.target.value })} className="input" /></div>
            <div><label className="label">Organisation</label><input value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} className="input" /></div>
            <div><label className="label">Visiting (host)</label><input value={form.host_name} onChange={(e) => setForm({ ...form, host_name: e.target.value })} className="input" /></div>
            <div><label className="label">Purpose</label><input value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} className="input" /></div>
            <div><label className="label">Phone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input" /></div>
            <div><label className="label">Badge No.</label><input value={form.badge_no} onChange={(e) => setForm({ ...form, badge_no: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.visitor_name.trim() || signIn.isPending} className="btn-primary gap-2">{signIn.isPending && <Loader2 size={15} className="animate-spin" />}Sign in</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Visitor", "Visiting", "Signed in", "Status", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load visitors.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((v) => (
                <tr key={v.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4"><p className="text-sm font-medium text-slate-800">{v.visitor_name}</p><p className="text-xs text-slate-400">{v.organization || v.purpose || ""}</p></td>
                  <td className="px-5 py-4 text-sm text-slate-600">{v.host_name || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{v.sign_in_at ? new Date(v.sign_in_at).toLocaleString() : "—"}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", v.status === "signed_in" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{v.status.replace("_", " ")}</span></td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-1">
                        {v.status === "signed_in" && <button onClick={() => signOut.mutate(v.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50"><LogOut size={13} /> Sign out</button>}
                        <button onClick={() => { if (confirm("Remove this visitor record? It will be soft-deleted and audited.")) del.mutate(v.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-16 text-center text-slate-400"><UserCheck size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No visitors logged</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function CollectionsTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useCollections();
  const record = useRecordCollection();
  const del = useDeleteCollection();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ student_id: "", collector_name: "", relationship_to_student: "", authorized_by: "", notes: "" });

  const reset = () => { setForm({ student_id: "", collector_name: "", relationship_to_student: "", authorized_by: "", notes: "" }); setShow(false); };
  const submit = () => record.mutate({ student_id: form.student_id, collector_name: form.collector_name.trim(), relationship_to_student: form.relationship_to_student || null, authorized_by: form.authorized_by, notes: form.notes || null }, { onSuccess: reset });

  const rows = data?.items;

  return (
    <>
      <div className="flex justify-end mb-4">{canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Record Collection</button>}</div>
      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4"><ShieldAlert size={14} /> A pickup must be authorised by a staff member — recorded for safeguarding.</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Collector Name *</label><input value={form.collector_name} onChange={(e) => setForm({ ...form, collector_name: e.target.value })} className="input" /></div>
            <div><label className="label">Relationship</label><input value={form.relationship_to_student} onChange={(e) => setForm({ ...form, relationship_to_student: e.target.value })} className="input" placeholder="parent / aunt / driver" /></div>
            <div><label className="label">Authorised by (staff) *</label><EntityPicker type="staff" value={form.authorized_by || null} onChange={(id) => setForm({ ...form, authorized_by: id || "" })} /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.student_id || !form.collector_name.trim() || !form.authorized_by || record.isPending} className="btn-primary gap-2">{record.isPending && <Loader2 size={15} className="animate-spin" />}Record</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Collected by", "Authorised by", "When", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load records.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{c.student_name || c.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-700">{c.collector_name}<span className="text-xs text-slate-400">{c.relationship_to_student ? ` · ${c.relationship_to_student}` : ""}</span></td>
                  <td className="px-5 py-4 text-sm text-slate-600">{c.authorized_by_name || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{c.collected_at ? new Date(c.collected_at).toLocaleString() : formatDate(c.created_at)}</td>
                  <td className="px-5 py-4">{canWrite && <button onClick={() => { if (confirm("Remove this collection record? It will be soft-deleted and audited.")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-16 text-center text-slate-400"><ShieldAlert size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No collections recorded</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
