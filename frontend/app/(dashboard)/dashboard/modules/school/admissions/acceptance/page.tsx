"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useAcceptanceForms, useCreateAcceptance, useUpdateAcceptance,
  useApplications, useClassOptions,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { ArrowLeft, Plus, X, Loader2, ClipboardCheck } from "lucide-react";
import type { AcceptanceForm, AdmissionApplication } from "@/types";

const STATUSES = ["pending", "accepted", "declined", "expired"];
const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  accepted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  declined: "bg-rose-50 text-rose-700 border-rose-200",
  expired: "bg-slate-50 text-slate-600 border-slate-200",
};

type FormState = {
  offered_class_id: string; offered_level: string;
  offer_date: string; acceptance_deadline: string; resumption_date: string;
  acceptance_fee_amount: string; fee_status: string; payment_reference: string;
  terms_text: string; status: string; accepted_by: string; decline_reason: string;
};

const EMPTY: FormState = {
  offered_class_id: "", offered_level: "", offer_date: "", acceptance_deadline: "",
  resumption_date: "", acceptance_fee_amount: "0", fee_status: "unpaid", payment_reference: "",
  terms_text: "", status: "pending", accepted_by: "", decline_reason: "",
};

export default function AcceptancePage() {
  const canWrite = useHasPermission("school:admissions:write");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [appId, setAppId] = useState("");
  const [form, setForm] = useState<FormState>({ ...EMPTY });

  const { data, isLoading } = useAcceptanceForms({ status: statusFilter || undefined, page: 1, page_size: 100 });
  const { data: appsData } = useApplications({ page: 1, page_size: 200 });
  const { data: classData } = useClassOptions();
  const create = useCreateAcceptance();
  const update = useUpdateAcceptance();

  const rows: AcceptanceForm[] = data?.items || [];
  // Only offered/admitted applications can raise an acceptance form (backend-gated).
  const eligibleApps: AdmissionApplication[] = (appsData?.items || []).filter(
    (a: AdmissionApplication) => a.status === "offered" || a.status === "admitted",
  );
  const classes = classData?.items || classData || [];

  const reset = () => { setForm({ ...EMPTY }); setEditId(null); setAppId(""); setShowForm(false); };

  const startEdit = (a: AcceptanceForm) => {
    setEditId(a.id);
    setAppId(a.application_id);
    setForm({
      offered_class_id: a.offered_class_id || "", offered_level: a.offered_level || "",
      offer_date: a.offer_date || "", acceptance_deadline: a.acceptance_deadline || "",
      resumption_date: a.resumption_date || "",
      acceptance_fee_amount: String(a.acceptance_fee_amount ?? 0), fee_status: a.fee_status || "unpaid",
      payment_reference: a.payment_reference || "", terms_text: a.terms_text || "",
      status: a.status, accepted_by: a.accepted_by || "", decline_reason: a.decline_reason || "",
    });
    setShowForm(true);
  };

  const onPickApp = (id: string) => {
    setAppId(id);
    const a = eligibleApps.find((x) => x.id === id);
    if (a) {
      setForm((prev) => ({
        ...prev,
        offered_class_id: prev.offered_class_id || (a.applying_for_class_id || ""),
        offered_level: prev.offered_level || (a.applying_for_level || ""),
      }));
    }
  };

  const submit = () => {
    const payload: Record<string, unknown> = {
      offered_class_id: form.offered_class_id || null,
      offered_level: form.offered_level || null,
      offer_date: form.offer_date || null,
      acceptance_deadline: form.acceptance_deadline || null,
      resumption_date: form.resumption_date || null,
      acceptance_fee_amount: Number(form.acceptance_fee_amount) || 0,
      fee_status: form.fee_status,
      payment_reference: form.payment_reference || null,
      terms_text: form.terms_text || null,
      status: form.status,
      accepted_by: form.accepted_by || null,
      decline_reason: form.decline_reason || null,
    };
    if (editId) {
      update.mutate({ id: editId, data: payload }, { onSuccess: reset });
    } else {
      create.mutate({ ...payload, application_id: appId }, { onSuccess: reset });
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/admissions" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Admissions</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Admissions</span><span>/</span><span className="text-brand-600 font-semibold">Acceptance Form</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Acceptance Form</h1>
          <p className="text-slate-500 text-sm mt-0.5">Offer &amp; acceptance for applicants who have been offered a place.</p>
        </div>
        {canWrite && !showForm && <button onClick={() => { reset(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Form</button>}
      </div>

      <div className="mb-5 flex bg-slate-100 rounded-lg p-0.5 w-fit">
        {[["", "All"], ...STATUSES.map((s) => [s, s[0].toUpperCase() + s.slice(1)])].map(([val, label]) => (
          <button key={val || "all"} onClick={() => setStatusFilter(val)}
            className={cn("px-3 py-1.5 text-xs font-semibold rounded-md capitalize transition-colors", statusFilter === val ? "bg-white shadow text-slate-900" : "text-slate-500 hover:text-slate-700")}>
            {label}
          </button>
        ))}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editId ? "Edit acceptance form" : "New acceptance form"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>

          {!editId && (
            <div className="mb-5 max-w-md">
              <label className="label">Application * <span className="text-slate-400 font-normal">(offered / admitted only)</span></label>
              {eligibleApps.length === 0 ? (
                <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-3">
                  No applications are at the offer stage yet. Mark an application as <strong>Offered</strong> in{" "}
                  <Link href="/dashboard/modules/school/admissions" className="text-brand-600 font-semibold hover:underline">Admissions &amp; Enquiries</Link> first.
                </p>
              ) : (
                <select value={appId} onChange={(e) => onPickApp(e.target.value)} className="input">
                  <option value="">— Select applicant —</option>
                  {eligibleApps.map((a) => <option key={a.id} value={a.id}>{a.full_name} · {a.status}</option>)}
                </select>
              )}
            </div>
          )}

          <div className="space-y-6">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Offer</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="label">Offered class</label>
                  <select value={form.offered_class_id} onChange={(e) => setForm({ ...form, offered_class_id: e.target.value })} className="input">
                    <option value="">—</option>
                    {classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div><label className="label">Offered level</label><input value={form.offered_level} onChange={(e) => setForm({ ...form, offered_level: e.target.value })} className="input" /></div>
                <div><label className="label">Offer date</label><input type="date" value={form.offer_date} onChange={(e) => setForm({ ...form, offer_date: e.target.value })} className="input" /></div>
                <div><label className="label">Acceptance deadline</label><input type="date" value={form.acceptance_deadline} onChange={(e) => setForm({ ...form, acceptance_deadline: e.target.value })} className="input" /></div>
                <div><label className="label">Resumption date</label><input type="date" value={form.resumption_date} onChange={(e) => setForm({ ...form, resumption_date: e.target.value })} className="input" /></div>
              </div>
            </div>

            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Acceptance fee</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div><label className="label">Amount</label><input type="number" value={form.acceptance_fee_amount} onChange={(e) => setForm({ ...form, acceptance_fee_amount: e.target.value })} className="input" /></div>
                <div>
                  <label className="label">Fee status</label>
                  <select value={form.fee_status} onChange={(e) => setForm({ ...form, fee_status: e.target.value })} className="input capitalize">
                    <option value="unpaid">Unpaid</option><option value="paid">Paid</option>
                  </select>
                </div>
                <div><label className="label">Payment reference</label><input value={form.payment_reference} onChange={(e) => setForm({ ...form, payment_reference: e.target.value })} className="input" /></div>
              </div>
            </div>

            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Acceptance</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="label">Status</label>
                  <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div><label className="label">Accepted by</label><input value={form.accepted_by} onChange={(e) => setForm({ ...form, accepted_by: e.target.value })} className="input" placeholder="Parent / guardian name" /></div>
                <div><label className="label">Decline reason</label><input value={form.decline_reason} onChange={(e) => setForm({ ...form, decline_reason: e.target.value })} className="input" /></div>
                <div className="md:col-span-3"><label className="label">Terms</label><textarea value={form.terms_text} onChange={(e) => setForm({ ...form, terms_text: e.target.value })} className="input" rows={2} /></div>
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-400 mt-4">Accepting does not admit the student — trigger the admit flow in Admissions &amp; Enquiries after confirming acceptance.</p>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={(!editId && !appId) || create.isPending || update.isPending} className="btn-primary gap-2">
              {(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />} {editId ? "Save" : "Create"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><ClipboardCheck size={30} className="mx-auto mb-2 opacity-50" />No acceptance forms yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">
              {["Candidate", "Offered class", "Fee", "Status", "Accepted", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-bold text-slate-900">{a.candidate_name || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{a.offered_class_name || a.offered_level || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">
                    <span className="tabular-nums">{Number(a.acceptance_fee_amount).toLocaleString()}</span>
                    <span className={cn("ml-2 badge capitalize", a.fee_status === "paid" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200")}>{a.fee_status}</span>
                  </td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[a.status])}>{a.status}</span></td>
                  <td className="px-5 py-4 text-xs text-slate-500">{a.accepted_at ? formatDate(a.accepted_at) : "—"}</td>
                  <td className="px-5 py-4 text-right">
                    {canWrite && <button onClick={() => startEdit(a)} className="text-xs font-semibold text-brand-600 hover:underline">Edit</button>}
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
