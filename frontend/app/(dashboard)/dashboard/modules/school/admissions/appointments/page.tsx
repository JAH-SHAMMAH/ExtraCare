"use client";

import { useState } from "react";
import Link from "next/link";
import { useApplications, useUpdateApplication } from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { ArrowLeft, X, Loader2, CalendarClock, CalendarPlus } from "lucide-react";
import type { AdmissionApplication } from "@/types";

const TABS = [
  ["all", "All enquiries"], ["scheduled", "Scheduled"],
  ["attended", "Attended"], ["no_show", "No-show"],
] as const;

const APPT_STATUSES = ["none", "scheduled", "attended", "no_show"];
const APPT_STYLE: Record<string, string> = {
  none: "bg-slate-50 text-slate-500 border-slate-200",
  scheduled: "bg-blue-50 text-blue-700 border-blue-200",
  attended: "bg-emerald-50 text-emerald-700 border-emerald-200",
  no_show: "bg-rose-50 text-rose-700 border-rose-200",
};

// ISO <-> <input type="datetime-local"> (which is local, no timezone suffix).
function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function EnquiryAppointmentPage() {
  const canWrite = useHasPermission("school:admissions:write");
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("all");
  const [editing, setEditing] = useState<AdmissionApplication | null>(null);
  const [form, setForm] = useState({ appointment_at: "", appointment_status: "scheduled", appointment_notes: "" });

  const { data, isLoading } = useApplications({
    ...(tab === "all" ? {} : { appointment_status: tab }),
    page: 1, page_size: 100,
  });
  const update = useUpdateApplication();
  const rows: AdmissionApplication[] = data?.items || [];

  const openEditor = (a: AdmissionApplication) => {
    setForm({
      appointment_at: isoToLocalInput(a.appointment_at),
      appointment_status: a.appointment_status === "none" ? "scheduled" : a.appointment_status,
      appointment_notes: a.appointment_notes || "",
    });
    setEditing(a);
  };

  const submit = () => {
    if (!editing) return;
    update.mutate({
      id: editing.id,
      data: {
        // datetime-local is local wall-clock; Date() reads it as local, toISOString normalises to UTC.
        appointment_at: form.appointment_at ? new Date(form.appointment_at).toISOString() : null,
        appointment_status: form.appointment_status,
        appointment_notes: form.appointment_notes || null,
      },
    }, { onSuccess: () => setEditing(null) });
  };

  const clearAppointment = (a: AdmissionApplication) => {
    update.mutate({ id: a.id, data: { appointment_at: null, appointment_status: "none", appointment_notes: null } });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/admissions" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Admissions & Enquiries</Link>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Enquiry Appointment</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Enquiry Appointment</h1>
        <p className="text-slate-500 text-sm mt-0.5">Schedule and track visits/interviews with prospective families.</p>
      </div>

      <div className="mb-5 flex bg-slate-100 rounded-lg p-0.5 w-fit">
        {TABS.map(([val, label]) => (
          <button
            key={val}
            onClick={() => setTab(val)}
            className={cn(
              "px-3 py-1.5 text-xs font-semibold rounded-md transition-colors",
              tab === val ? "bg-white shadow text-slate-900" : "text-slate-500 hover:text-slate-700",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {editing && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">Appointment — {editing.full_name}</h2>
            <button onClick={() => setEditing(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Date &amp; time</label><input type="datetime-local" value={form.appointment_at} onChange={(e) => setForm({ ...form, appointment_at: e.target.value })} className="input" /></div>
            <div>
              <label className="label">Status</label>
              <select value={form.appointment_status} onChange={(e) => setForm({ ...form, appointment_status: e.target.value })} className="input capitalize">
                {APPT_STATUSES.filter((s) => s !== "none").map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={form.appointment_notes} onChange={(e) => setForm({ ...form, appointment_notes: e.target.value })} className="input" rows={2} placeholder="Purpose, who's attending…" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setEditing(null)} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={update.isPending} className="btn-primary gap-2">
              {update.isPending && <Loader2 size={15} className="animate-spin" />} Save appointment
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><CalendarClock size={30} className="mx-auto mb-2 opacity-50" />No enquiries in this view.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">
              {["Applicant", "Guardian", "Appointment", "Status", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{a.full_name}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{a.guardian_name || "—"}{a.guardian_phone && <span className="block text-xs text-slate-400">{a.guardian_phone}</span>}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{a.appointment_at ? new Date(a.appointment_at).toLocaleString() : <span className="text-slate-300">—</span>}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", APPT_STYLE[a.appointment_status] || APPT_STYLE.none)}>{(a.appointment_status || "none").replace("_", " ")}</span></td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => openEditor(a)} className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 hover:text-brand-700">
                          <CalendarPlus size={14} /> {a.appointment_status === "none" ? "Schedule" : "Reschedule"}
                        </button>
                        {a.appointment_status !== "none" && (
                          <button onClick={() => clearAppointment(a)} className="text-xs text-slate-400 hover:text-rose-600">Clear</button>
                        )}
                      </div>
                    )}
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
