"use client";

import { useState } from "react";
import Link from "next/link";
import { CalendarClock, Plus, Loader2 } from "lucide-react";
import { useLeaveApplications, useCreateLeave } from "@/hooks/useLeave";
import { StatusPill } from "./StatusPill";
import type { LeaveApplication, LeaveType } from "@/types";

const LEAVE_TYPES: { value: LeaveType; label: string }[] = [
  { value: "annual", label: "Annual" },
  { value: "casual", label: "Casual" },
  { value: "sick", label: "Sick" },
  { value: "maternity", label: "Maternity" },
  { value: "paternity", label: "Paternity" },
  { value: "bereavement", label: "Bereavement" },
  { value: "unpaid", label: "Unpaid" },
  { value: "other", label: "Other" },
];

export default function MyLeavePage() {
  const { data: rows = [], isLoading } = useLeaveApplications({ mine: true, limit: 100 });
  const create = useCreateLeave();

  const [form, setForm] = useState<{
    leave_type: LeaveType;
    start_date: string;
    end_date: string;
    reason: string;
  }>({
    leave_type: "annual",
    start_date: "",
    end_date: "",
    reason: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.start_date || !form.end_date) return;
    create.mutate(
      {
        leave_type: form.leave_type,
        start_date: form.start_date,
        end_date: form.end_date,
        reason: form.reason || null,
      },
      {
        onSuccess: () => {
          setForm({ leave_type: "annual", start_date: "", end_date: "", reason: "" });
        },
      },
    );
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-5xl mx-auto">
      <header>
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <Link href="/dashboard/hrm" className="hover:text-brand-600">HRM</Link>
          <span>/</span>
          <span className="text-brand-600 font-semibold">My Leave</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Leave Applications</h1>
        <p className="text-slate-500 text-sm mt-0.5">Apply for leave and track your requests.</p>
      </header>

      {/* Apply form */}
      <section className="bg-white rounded-xl border border-slate-200 p-6">
        <header className="flex items-center gap-2 mb-4">
          <Plus className="w-4 h-4 text-brand-600" />
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide">New Application</h2>
        </header>
        <form onSubmit={handleSubmit} className="grid md:grid-cols-4 gap-3 items-end">
          <Select
            label="Leave Type"
            value={form.leave_type}
            onChange={(v) => setForm({ ...form, leave_type: v as LeaveType })}
            options={LEAVE_TYPES}
          />
          <Input
            label="Start Date" type="date" required
            value={form.start_date} onChange={(v) => setForm({ ...form, start_date: v })}
          />
          <Input
            label="End Date" type="date" required
            value={form.end_date} onChange={(v) => setForm({ ...form, end_date: v })}
          />
          <button
            type="submit"
            disabled={create.isPending}
            className="bg-brand-600 hover:bg-brand-700 text-white font-semibold px-4 py-2 rounded-lg disabled:opacity-50 inline-flex items-center justify-center gap-2"
          >
            {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Apply
          </button>
          <div className="md:col-span-4">
            <label className="block">
              <span className="text-xs font-semibold text-slate-600 mb-1 block">Reason (optional)</span>
              <textarea
                rows={2}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
              />
            </label>
          </div>
        </form>
      </section>

      {/* History */}
      <section className="bg-white rounded-xl border border-slate-200 p-6">
        <header className="flex items-center gap-2 mb-4">
          <CalendarClock className="w-4 h-4 text-brand-600" />
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide">My Applications</h2>
        </header>
        {isLoading ? (
          <p className="text-sm text-slate-500 py-4">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-500 italic py-4">No applications yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Dates</th>
                  <th className="py-2 pr-4">Days</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Decision Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r: LeaveApplication) => (
                  <tr key={r.id}>
                    <td className="py-2 pr-4 capitalize">{r.leave_type}</td>
                    <td className="py-2 pr-4">{r.start_date} → {r.end_date}</td>
                    <td className="py-2 pr-4">{r.days}</td>
                    <td className="py-2 pr-4"><StatusPill status={r.status} /></td>
                    <td className="py-2 pr-4 text-slate-500">{r.decision_note || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Input({
  label, value, onChange, type = "text", required,
}: { label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600 mb-1 block">{label}</span>
      <input
        type={type} required={required} value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
      />
    </label>
  );
}

function Select<T extends string>({
  label, value, onChange, options,
}: { label: string; value: T; onChange: (v: T) => void; options: { value: T; label: string }[] }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600 mb-1 block">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}
