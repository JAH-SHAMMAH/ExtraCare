"use client";

import { useState } from "react";
import {
  useDevices, useCreateDevice, useDeleteDevice,
  useEnrollments, useCreateEnrollment, useDeleteEnrollment,
  useQuarantine, useResolvePunch, useDiscardPunch,
} from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { Activity, Plus, X, Loader2, Trash2, AlertTriangle, Clock, Check, Ban } from "lucide-react";
import type { UnmappedPunch } from "@/types";

type Tab = "devices" | "enrollments" | "quarantine";

export default function BiometricPage() {
  const canWrite = useHasPermission("settings:write");
  const [tab, setTab] = useState<Tab>("devices");
  const { data: quarantine } = useQuarantine();
  const pending = (quarantine ?? []).length;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">Biometric Devices</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Biometric Devices</h1>
        <p className="text-slate-500 text-sm mt-0.5">ZKTeco terminals → attendance events. Punches dedupe on the device record id; unmapped punches quarantine for review.</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["devices", "Devices"], ["enrollments", "Enrollments"], ["quarantine", `Needs review${pending ? ` (${pending})` : ""}`]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {tab === "devices" ? <DevicesTab canWrite={canWrite} /> : tab === "enrollments" ? <EnrollmentsTab canWrite={canWrite} /> : <QuarantineTab canWrite={canWrite} />}
    </div>
  );
}

function DevicesTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useDevices();
  const create = useCreateDevice();
  const del = useDeleteDevice();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ device_id: "", name: "", location: "" });
  const reset = () => { setForm({ device_id: "", name: "", location: "" }); setShow(false); };

  return (
    <>
      <div className="flex justify-end mb-4">{canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Register Device</button>}</div>
      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div><label className="label">Device ID *</label><input value={form.device_id} onChange={(e) => setForm({ ...form, device_id: e.target.value })} className="input" placeholder="serial" /></div>
          <div><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
          <div><label className="label">Location</label><input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="input" /></div>
          <button onClick={() => create.mutate({ device_id: form.device_id.trim(), name: form.name.trim(), location: form.location || null }, { onSuccess: reset })} disabled={!form.device_id.trim() || !form.name.trim() || create.isPending} className="btn-primary justify-center">Register</button>
        </div>
      )}
      {isLoading ? <Skel /> : isError ? <ErrBox onRetry={refetch} /> : (data ?? []).length > 0 ? (
        <Table head={["Device", "Location", "Last seen", "Clock skew", "Status", ""]}>
          {data!.map((d) => (
            <tr key={d.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-4"><p className="text-sm font-semibold text-slate-800">{d.name}</p><p className="text-xs font-mono text-slate-400">{d.device_id}</p></td>
              <td className="px-5 py-4 text-sm text-slate-600">{d.location || "—"}</td>
              <td className="px-5 py-4 text-xs text-slate-500">{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "never"}</td>
              <td className="px-5 py-4">{d.clock_skew_seconds != null && Math.abs(d.clock_skew_seconds) > 300 ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600"><Clock size={12} /> {d.clock_skew_seconds}s drift</span> : <span className="text-xs text-slate-400">{d.clock_skew_seconds != null ? `${d.clock_skew_seconds}s` : "—"}</span>}</td>
              <td className="px-5 py-4"><span className={cn("badge", d.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{d.is_active ? "Active" : "Inactive"}</span></td>
              <td className="px-5 py-4">{canWrite && <button onClick={() => { if (confirm("Remove device?")) del.mutate(d.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
            </tr>
          ))}
        </Table>
      ) : <Empty icon={Activity} label="No devices registered" />}
    </>
  );
}

function EnrollmentsTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useEnrollments();
  const create = useCreateEnrollment();
  const del = useDeleteEnrollment();
  const [form, setForm] = useState({ biometric_user_id: "", student_id: "", label: "" });

  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div><label className="label">Biometric ID *</label><input value={form.biometric_user_id} onChange={(e) => setForm({ ...form, biometric_user_id: e.target.value })} className="input" placeholder="device user id" /></div>
          <div className="md:col-span-2"><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
          <button onClick={() => create.mutate({ biometric_user_id: form.biometric_user_id.trim(), student_id: form.student_id, label: form.label || null }, { onSuccess: () => setForm({ biometric_user_id: "", student_id: "", label: "" }) })} disabled={!form.biometric_user_id.trim() || !form.student_id || create.isPending} className="btn-primary justify-center">Map</button>
        </div>
      )}
      {isLoading ? <Skel /> : isError ? <ErrBox onRetry={refetch} /> : (data ?? []).length > 0 ? (
        <Table head={["Biometric ID", "Student", ""]}>
          {data!.map((e) => (
            <tr key={e.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-4 text-sm font-mono text-slate-600">{e.biometric_user_id}</td>
              <td className="px-5 py-4 text-sm text-slate-800">{e.student_name || e.student_id.slice(0, 8)}</td>
              <td className="px-5 py-4">{canWrite && <button onClick={() => del.mutate(e.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
            </tr>
          ))}
        </Table>
      ) : <Empty icon={Activity} label="No enrollments yet" />}
    </>
  );
}

function QuarantineTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useQuarantine();
  const resolve = useResolvePunch();
  const discard = useDiscardPunch();
  const [resolving, setResolving] = useState<UnmappedPunch | null>(null);
  const [studentId, setStudentId] = useState("");

  return (
    <>
      <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4"><AlertTriangle size={14} /> Punches from unknown devices/ids are held here — never dropped, never auto-assigned. Resolve to a student or discard.</div>
      {resolving && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setResolving(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Resolve punch ({resolving.biometric_user_id || "—"})</h3><button onClick={() => setResolving(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4"><label className="label">Assign to student *</label><EntityPicker type="student" value={studentId || null} onChange={(id) => setStudentId(id || "")} /><p className="text-xs text-slate-400 mt-2">This also enrolls the biometric id for future punches.</p></div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setResolving(null)} className="btn-secondary">Cancel</button><button onClick={() => resolve.mutate({ id: resolving.id, data: { student_id: studentId, enroll: true } }, { onSuccess: () => { setResolving(null); setStudentId(""); } })} disabled={!studentId || resolve.isPending} className="btn-primary gap-2">{resolve.isPending && <Loader2 size={15} className="animate-spin" />}Resolve + replay</button></div>
          </div>
        </div>
      )}
      {isLoading ? <Skel /> : isError ? <ErrBox onRetry={refetch} /> : (data ?? []).length > 0 ? (
        <Table head={["Device", "Biometric ID", "When", "Reason", "Actions"]}>
          {data!.map((p) => (
            <tr key={p.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-4 text-sm font-mono text-slate-600">{p.device_id || "—"}</td>
              <td className="px-5 py-4 text-sm font-mono text-slate-600">{p.biometric_user_id || "—"}</td>
              <td className="px-5 py-4 text-xs text-slate-500">{p.event_time ? new Date(p.event_time).toLocaleString() : "—"}</td>
              <td className="px-5 py-4"><span className="badge bg-amber-50 text-amber-700 border-amber-200">{p.reason.replace(/_/g, " ")}</span></td>
              <td className="px-5 py-4">{canWrite && (
                <div className="flex items-center gap-1">
                  <button onClick={() => { setResolving(p); setStudentId(""); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><Check size={13} /> Resolve</button>
                  <button onClick={() => { if (confirm("Discard this punch?")) discard.mutate(p.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100"><Ban size={13} /> Discard</button>
                </div>
              )}</td>
            </tr>
          ))}
        </Table>
      ) : <Empty icon={Check} label="Nothing to review" />}
    </>
  );
}

// shared bits
function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <table className="w-full text-left">
        <thead><tr className="bg-slate-50/80 border-b border-slate-100">{head.map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-50">{children}</tbody>
      </table>
    </div>
  );
}
function Skel() { return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>; }
function ErrBox({ onRetry }: { onRetry: () => void }) { return <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load.</p><button onClick={onRetry} className="mt-3 btn-secondary">Retry</button></div>; }
function Empty({ icon: Icon, label }: { icon: any; label: string }) { return <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Icon size={36} className="mb-3 opacity-40" /><p className="font-semibold">{label}</p></div>; }
