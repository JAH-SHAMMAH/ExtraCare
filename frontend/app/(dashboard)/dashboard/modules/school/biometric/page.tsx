"use client";

import { useState } from "react";
import {
  useDevices, useCreateDevice, useUpdateDevice, useDeleteDevice, useIssueDeviceToken, useRevokeDeviceToken,
  useEnrollments, useCreateEnrollment, useDeleteEnrollment,
  useQuarantine, useResolvePunch, useDiscardPunch,
  useBiometricSummary, useAttendanceHistory, useBiometricCommands, useGenerateCommand, useDeleteCommand,
} from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  Activity, Plus, X, Loader2, Trash2, AlertTriangle, Clock, Check, Ban, KeyRound, Copy,
  Fingerprint, ScanFace, CreditCard, Users, Cpu, Terminal, Pencil, LogIn, LogOut,
} from "lucide-react";
import type { UnmappedPunch, DeviceToken, BiometricDevice } from "@/types";

type Tab = "home" | "users" | "attendance" | "device" | "review";

// Common terminal commands surfaced by the "Generate Biometric Command" action.
const COMMAND_PRESETS = [
  "Backup User Data from device",
  "Restore User Data to device",
  "Sync Device Time",
  "Clear Attendance Log",
  "Restart Device",
  "Enroll New User",
];

export default function BiometricPage() {
  const canWrite = useHasPermission("settings:write");
  const [tab, setTab] = useState<Tab>("home");
  const { data: devices } = useDevices();
  const { data: quarantine } = useQuarantine();
  const pending = (quarantine ?? []).length;

  // A single device selector drives Home (commands), Attendance and Device Information.
  const [deviceId, setDeviceId] = useState<string>(""); // "" = all devices
  const selected = (devices ?? []).find((d) => d.id === deviceId) || null;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">Manage Biometric</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Biometric</h1>
          <p className="text-slate-500 text-sm mt-0.5">Registered devices, users, attendance events and device commands.</p>
        </div>
        {(devices ?? []).length > 0 && (
          <div>
            <label className="label">Device</label>
            <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)} className="input min-w-[220px]">
              <option value="">All devices</option>
              {devices!.map((d) => <option key={d.id} value={d.id}>{d.name} · {d.model_name || d.device_id}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
        {([
          ["home", "Home"],
          ["users", "Registered Users"],
          ["attendance", "Attendance History"],
          ["device", "Device Information"],
          ["review", `Needs review${pending ? ` (${pending})` : ""}`],
        ] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition whitespace-nowrap", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>

      {tab === "home" ? <HomeTab canWrite={canWrite} devices={devices ?? []} selected={selected} />
        : tab === "users" ? <UsersTab canWrite={canWrite} />
        : tab === "attendance" ? <AttendanceTab selected={selected} />
        : tab === "device" ? <DeviceTab canWrite={canWrite} devices={devices ?? []} selected={selected} onSelect={setDeviceId} />
        : <ReviewTab canWrite={canWrite} />}
    </div>
  );
}

// ── Home ─────────────────────────────────────────────────────────────────────────
function HomeTab({ canWrite, devices, selected }: { canWrite: boolean; devices: BiometricDevice[]; selected: BiometricDevice | null }) {
  const { data: sum } = useBiometricSummary();
  const { data: commands, isLoading, isError, refetch } = useBiometricCommands(selected?.id);
  const gen = useGenerateCommand();
  const del = useDeleteCommand();
  const [show, setShow] = useState(false);
  const [cmd, setCmd] = useState(COMMAND_PRESETS[0]);
  const [target, setTarget] = useState<string>(selected?.id || (devices[0]?.id ?? ""));

  const cards: [string, number | undefined, any, string][] = [
    ["Total Devices", sum?.total_devices, Cpu, "text-slate-600"],
    ["Device Users", sum?.total_device_users, Users, "text-brand-600"],
    ["Fingerprint", sum?.total_fingerprint, Fingerprint, "text-indigo-600"],
    ["Face", sum?.total_face, ScanFace, "text-violet-600"],
    ["Card", sum?.total_card, CreditCard, "text-cyan-600"],
    ["Active Users", sum?.total_active_users, Check, "text-emerald-600"],
    ["Total Attendance", sum?.total_attendance, Activity, "text-amber-600"],
  ];

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mb-6">
        {cards.map(([label, value, Icon, color]) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <Icon size={18} className={cn("mb-2", color)} />
            <p className="text-2xl font-black text-slate-900 tabular-nums">{value ?? "—"}</p>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2"><Terminal size={15} className="text-brand-600" /> Device Commands{selected ? ` · ${selected.name}` : ""}</h2>
        {canWrite && devices.length > 0 && <button onClick={() => { setTarget(selected?.id || devices[0].id); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Generate Biometric Command</button>}
      </div>

      {show && canWrite && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setShow(false)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Generate Biometric Command</h3><button onClick={() => setShow(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 space-y-3">
              <div><label className="label">Device *</label>
                <select value={target} onChange={(e) => setTarget(e.target.value)} className="input">
                  {devices.map((d) => <option key={d.id} value={d.id}>{d.name} · {d.model_name || d.device_id}</option>)}
                </select>
              </div>
              <div><label className="label">Command *</label>
                <select value={cmd} onChange={(e) => setCmd(e.target.value)} className="input">
                  {COMMAND_PRESETS.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <p className="text-xs text-slate-400">The device polls its command queue on next sync and acknowledges the result.</p>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100">
              <button onClick={() => setShow(false)} className="btn-secondary">Cancel</button>
              <button onClick={() => gen.mutate({ devicePk: target, data: { command: cmd } }, { onSuccess: () => setShow(false) })} disabled={!target || gen.isPending} className="btn-primary gap-2">{gen.isPending && <Loader2 size={15} className="animate-spin" />}Queue command</button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? <Skel /> : isError ? <ErrBox onRetry={refetch} /> : (commands ?? []).length > 0 ? (
        <Table head={["Device", "Command", "Status", "Result", "Queued", ""]}>
          {commands!.map((c) => (
            <tr key={c.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-4 text-sm font-mono text-slate-600">{c.device_id || c.device_pk.slice(0, 8)}</td>
              <td className="px-5 py-4 text-sm text-slate-800">{c.command}</td>
              <td className="px-5 py-4"><span className={cn("badge", c.status === "done" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : c.status === "failed" ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200")}>{c.status}</span></td>
              <td className="px-5 py-4 text-xs text-slate-500 max-w-[200px] truncate">{c.result || "—"}</td>
              <td className="px-5 py-4 text-xs text-slate-500">{new Date(c.created_at).toLocaleString()}</td>
              <td className="px-5 py-4">{canWrite && <button onClick={() => del.mutate(c.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
            </tr>
          ))}
        </Table>
      ) : <Empty icon={Terminal} label="No commands queued" />}
    </>
  );
}

// ── Registered Users ───────────────────────────────────────────────────────────────
function UsersTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useEnrollments();
  const create = useCreateEnrollment();
  const del = useDeleteEnrollment();
  const empty = { biometric_user_id: "", kind: "student" as "student" | "staff", person_id: "", label: "", fingerprint_count: 0, has_face: false, has_card: false };
  const [form, setForm] = useState(empty);

  const submit = () => {
    const base: any = { biometric_user_id: form.biometric_user_id.trim(), label: form.label || null, fingerprint_count: form.fingerprint_count, has_face: form.has_face, has_card: form.has_card };
    if (form.kind === "student") base.student_id = form.person_id; else base.user_id = form.person_id;
    create.mutate(base, { onSuccess: () => setForm(empty) });
  };

  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div><label className="label">Biometric ID *</label><input value={form.biometric_user_id} onChange={(e) => setForm({ ...form, biometric_user_id: e.target.value })} className="input" placeholder="device user id" /></div>
            <div><label className="label">Type</label>
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as "student" | "staff", person_id: "" })} className="input">
                <option value="student">Student</option>
                <option value="staff">Staff</option>
              </select>
            </div>
            <div className="md:col-span-2"><label className="label">{form.kind === "student" ? "Student" : "Staff member"} *</label>
              <EntityPicker type={form.kind} value={form.person_id || null} onChange={(id) => setForm({ ...form, person_id: id || "" })} />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div><label className="label">Fingerprints</label><input type="number" min={0} value={form.fingerprint_count} onChange={(e) => setForm({ ...form, fingerprint_count: Math.max(0, parseInt(e.target.value) || 0) })} className="input w-28" /></div>
            <label className="flex items-center gap-2 text-sm text-slate-600 pb-2"><input type="checkbox" checked={form.has_face} onChange={(e) => setForm({ ...form, has_face: e.target.checked })} /> Face enrolled</label>
            <label className="flex items-center gap-2 text-sm text-slate-600 pb-2"><input type="checkbox" checked={form.has_card} onChange={(e) => setForm({ ...form, has_card: e.target.checked })} /> Card enrolled</label>
            <button onClick={submit} disabled={!form.biometric_user_id.trim() || !form.person_id || create.isPending} className="btn-primary justify-center ml-auto">Register user</button>
          </div>
        </div>
      )}
      {isLoading ? <Skel /> : isError ? <ErrBox onRetry={refetch} /> : (data ?? []).length > 0 ? (
        <Table head={["Biometric ID", "Name", "Type / Role", "Fingerprint", "Face", "Card", "Status", ""]}>
          {data!.map((e) => (
            <tr key={e.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-4 text-sm font-mono text-slate-600">{e.biometric_user_id}</td>
              <td className="px-5 py-4 text-sm font-semibold text-slate-800">{e.person_name || (e.student_id || e.user_id || "").slice(0, 8)}</td>
              <td className="px-5 py-4"><span className={cn("badge", e.person_type === "staff" ? "bg-indigo-50 text-indigo-700 border-indigo-200" : "bg-brand-50 text-brand-700 border-brand-200")}>{e.person_type === "staff" ? (e.role_name || "Staff") : "Student"}</span></td>
              <td className="px-5 py-4 text-sm text-slate-600 tabular-nums">{e.fingerprint_count}</td>
              <td className="px-5 py-4">{e.has_face ? <Check size={15} className="text-emerald-600" /> : <span className="text-slate-300">—</span>}</td>
              <td className="px-5 py-4">{e.has_card ? <Check size={15} className="text-emerald-600" /> : <span className="text-slate-300">—</span>}</td>
              <td className="px-5 py-4"><span className="badge bg-slate-50 text-slate-500 border-slate-200">{e.status}</span></td>
              <td className="px-5 py-4">{canWrite && <button onClick={() => del.mutate(e.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
            </tr>
          ))}
        </Table>
      ) : <Empty icon={Users} label="No registered users yet" />}
    </>
  );
}

// ── Attendance History ─────────────────────────────────────────────────────────────
function AttendanceTab({ selected }: { selected: BiometricDevice | null }) {
  const { data, isLoading, isError, refetch } = useAttendanceHistory(selected?.device_id);
  return (
    <>
      <p className="text-xs text-slate-500 mb-4">Most recent 300 attendance events{selected ? ` from ${selected.name}` : " across all devices"}.</p>
      {isLoading ? <Skel /> : isError ? <ErrBox onRetry={refetch} /> : (data ?? []).length > 0 ? (
        <Table head={["Name", "Direction", "Time", "Mode", "Device"]}>
          {data!.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50/70">
              <td className="px-5 py-4 text-sm font-semibold text-slate-800">{r.name || r.student_id.slice(0, 8)}</td>
              <td className="px-5 py-4">{r.event_type === "check_out"
                ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500"><LogOut size={13} /> Check out</span>
                : <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600"><LogIn size={13} /> Check in</span>}</td>
              <td className="px-5 py-4 text-xs text-slate-500">{new Date(r.event_time).toLocaleString()}</td>
              <td className="px-5 py-4"><span className="badge bg-slate-50 text-slate-500 border-slate-200">{r.source}</span></td>
              <td className="px-5 py-4 text-xs font-mono text-slate-500">{r.device_id || "—"}</td>
            </tr>
          ))}
        </Table>
      ) : <Empty icon={Activity} label="No attendance events yet" />}
    </>
  );
}

// ── Device Information ─────────────────────────────────────────────────────────────
const SPEC_FIELDS: [keyof BiometricDevice, string, "text" | "number"][] = [
  ["model_name", "Model name", "text"],
  ["device_id", "Device ID", "text"],
  ["vendor", "Vendor", "text"],
  ["device_type", "Device type", "text"],
  ["volume", "Volume", "number"],
  ["language", "Language", "text"],
  ["fingerprint_version", "Fingerprint version", "text"],
  ["face_version", "Face version", "text"],
  ["firmware_version", "Firmware version", "text"],
  ["mac_address", "MAC address", "text"],
  ["storage_used_percent", "Storage used %", "number"],
  ["attendance_log_capacity", "Attendance log capacity", "number"],
  ["current_attendance_log", "Current attendance log", "number"],
];

function DeviceTab({ canWrite, devices, selected, onSelect }: { canWrite: boolean; devices: BiometricDevice[]; selected: BiometricDevice | null; onSelect: (id: string) => void }) {
  const create = useCreateDevice();
  const del = useDeleteDevice();
  const issueToken = useIssueDeviceToken();
  const revokeToken = useRevokeDeviceToken();
  const [showNew, setShowNew] = useState(false);
  const [nf, setNf] = useState({ device_id: "", name: "", location: "" });
  const [revealed, setRevealed] = useState<DeviceToken | null>(null);
  const device = selected || devices[0] || null;

  return (
    <>
      {revealed && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={() => setRevealed(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2"><KeyRound size={16} className="text-brand-600" /> Ingest token for {revealed.device_id}</h3>
              <button onClick={() => setRevealed(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700 mb-3">Copy this now — shown <strong>once</strong>. Configure it as the device/middleware <code>X-Device-Token</code> header.</div>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-slate-900 text-emerald-300 text-xs font-mono rounded-lg px-3 py-2.5 break-all">{revealed.token}</code>
              <button onClick={() => { navigator.clipboard?.writeText(revealed.token); toast.success("Token copied."); }} className="btn-secondary gap-1.5 shrink-0"><Copy size={14} /> Copy</button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          {devices.map((d) => (
            <button key={d.id} onClick={() => onSelect(d.id)} className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold border transition", device?.id === d.id ? "bg-brand-50 border-brand-200 text-brand-700" : "bg-white border-slate-200 text-slate-500 hover:text-slate-700")}>{d.name}</button>
          ))}
        </div>
        {canWrite && <button onClick={() => { setNf({ device_id: "", name: "", location: "" }); setShowNew(true); }} className="btn-primary gap-2"><Plus size={15} /> Register Device</button>}
      </div>

      {showNew && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div><label className="label">Device ID *</label><input value={nf.device_id} onChange={(e) => setNf({ ...nf, device_id: e.target.value })} className="input" placeholder="serial" /></div>
          <div><label className="label">Name *</label><input value={nf.name} onChange={(e) => setNf({ ...nf, name: e.target.value })} className="input" /></div>
          <div><label className="label">Location</label><input value={nf.location} onChange={(e) => setNf({ ...nf, location: e.target.value })} className="input" /></div>
          <div className="flex gap-2">
            <button onClick={() => create.mutate({ device_id: nf.device_id.trim(), name: nf.name.trim(), location: nf.location || null }, { onSuccess: () => setShowNew(false) })} disabled={!nf.device_id.trim() || !nf.name.trim() || create.isPending} className="btn-primary justify-center flex-1">Register</button>
            <button onClick={() => setShowNew(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {device ? <DeviceCard device={device} canWrite={canWrite} onDelete={() => del.mutate(device.id)} onIssue={() => issueToken.mutate(device.id, { onSuccess: (t) => setRevealed(t) })} onRevoke={() => { if (confirm(`Revoke the ingest token for ${device.device_id}?`)) revokeToken.mutate(device.id); }} issuing={issueToken.isPending} />
        : <Empty icon={Cpu} label="No devices registered" />}
    </>
  );
}

function DeviceCard({ device, canWrite, onDelete, onIssue, onRevoke, issuing }: { device: BiometricDevice; canWrite: boolean; onDelete: () => void; onIssue: () => void; onRevoke: () => void; issuing: boolean }) {
  const update = useUpdateDevice();
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState<any>({});

  const startEdit = () => {
    const seed: any = { name: device.name, location: device.location || "" };
    SPEC_FIELDS.forEach(([k]) => { if (k !== "device_id") seed[k] = device[k] ?? ""; });
    setForm(seed); setEdit(true);
  };
  const save = () => {
    const payload: any = { name: form.name, location: form.location || null };
    SPEC_FIELDS.forEach(([k, , type]) => {
      if (k === "device_id") return;
      const v = form[k];
      payload[k] = v === "" || v == null ? null : (type === "number" ? Number(v) : v);
    });
    update.mutate({ id: device.id, data: payload }, { onSuccess: () => setEdit(false) });
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
        <div>
          <h3 className="text-sm font-bold text-slate-800">{device.name}</h3>
          <p className="text-xs text-slate-400">{device.model_name || "Model not set"} · {device.location || "no location"}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("badge", device.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{device.is_active ? "Active" : "Inactive"}</span>
          {canWrite && !edit && <button onClick={startEdit} className="btn-secondary gap-1.5 py-1.5"><Pencil size={13} /> Edit</button>}
        </div>
      </div>

      {edit ? (
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
          <div><label className="label">Location</label><input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="input" /></div>
          {SPEC_FIELDS.filter(([k]) => k !== "device_id").map(([k, label, type]) => (
            <div key={k}><label className="label">{label}</label><input type={type} value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="input" /></div>
          ))}
          <div className="md:col-span-3 flex justify-end gap-3 pt-2">
            <button onClick={() => setEdit(false)} className="btn-secondary">Cancel</button>
            <button onClick={save} disabled={!form.name?.trim() || update.isPending} className="btn-primary gap-2">{update.isPending && <Loader2 size={15} className="animate-spin" />}Save</button>
          </div>
        </div>
      ) : (
        <>
          <dl className="p-6 grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
            {SPEC_FIELDS.map(([k, label]) => (
              <div key={k}>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
                <dd className="text-sm text-slate-800 mt-0.5">{device[k] != null && device[k] !== "" ? String(device[k]) : "—"}</dd>
              </div>
            ))}
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Last seen</dt>
              <dd className="text-sm text-slate-800 mt-0.5">{device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : "never"}</dd>
            </div>
          </dl>
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs">
              {device.has_token
                ? <><span className="inline-flex items-center gap-1 font-mono text-slate-600"><KeyRound size={12} className="text-emerald-600" />{device.token_prefix}…</span>
                    {canWrite && <>
                      <button onClick={onIssue} disabled={issuing} className="font-semibold text-brand-600 hover:underline">Rotate</button>
                      <button onClick={onRevoke} className="font-semibold text-red-500 hover:underline">Revoke</button>
                    </>}</>
                : canWrite
                  ? <button onClick={onIssue} disabled={issuing} className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:underline"><KeyRound size={12} /> Issue ingest token</button>
                  : <span className="text-slate-400">No ingest token</span>}
            </div>
            {canWrite && <button onClick={() => { if (confirm(`Remove ${device.name}?`)) onDelete(); }} className="inline-flex items-center gap-1 text-xs font-semibold text-red-500 hover:text-red-600"><Trash2 size={13} /> Remove device</button>}
          </div>
        </>
      )}
    </div>
  );
}

// ── Needs review (quarantine) ──────────────────────────────────────────────────────
function ReviewTab({ canWrite }: { canWrite: boolean }) {
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

// ── shared bits ────────────────────────────────────────────────────────────────────
function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
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
