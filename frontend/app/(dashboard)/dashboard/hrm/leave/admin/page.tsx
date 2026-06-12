"use client";

import { useState } from "react";
import Link from "next/link";
import { ShieldCheck, Check, X, Loader2, Inbox } from "lucide-react";
import {
  useLeaveApplications,
  useApproveLeave,
  useRejectLeave,
} from "@/hooks/useLeave";
import { StatusPill } from "../StatusPill";
import type { LeaveApplication, LeaveStatus } from "@/types";

const STATUS_TABS: { value: LeaveStatus | "all"; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

export default function LeaveAdminPage() {
  const [tab, setTab] = useState<LeaveStatus | "all">("pending");

  const { data: rows = [], isLoading, error } = useLeaveApplications({
    mine: false,
    status: tab === "all" ? undefined : tab,
    limit: 200,
  });

  const approve = useApproveLeave();
  const reject = useRejectLeave();

  const forbidden = (error as any)?.response?.status === 403;

  const handleDecide = (id: string, kind: "approve" | "reject") => {
    const note = window.prompt(`Optional note for ${kind}:`) || undefined;
    if (kind === "approve") approve.mutate({ id, note });
    else reject.mutate({ id, note });
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-6xl mx-auto">
      <header>
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <Link href="/dashboard/hrm" className="hover:text-brand-600">HRM</Link>
          <span>/</span>
          <Link href="/dashboard/hrm/leave" className="hover:text-brand-600">Leave</Link>
          <span>/</span>
          <span className="text-brand-600 font-semibold">Admin Queue</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-brand-600" />
          Leave Admin Queue
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Review and decide on leave applications across the organisation.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
              tab === t.value
                ? "bg-brand-600 text-white border-brand-600"
                : "bg-white text-slate-700 border-slate-200 hover:border-brand-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <section className="bg-white rounded-xl border border-slate-200 p-6">
        {forbidden ? (
          <EmptyState
            icon={<ShieldCheck className="w-8 h-8 text-rose-500" />}
            title="HR admin access required"
            hint="You need the users:read permission to view the organisation-wide queue."
          />
        ) : isLoading ? (
          <p className="text-sm text-slate-500 py-4">Loading…</p>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<Inbox className="w-8 h-8 text-slate-400" />}
            title={`No ${tab === "all" ? "" : tab} applications`}
            hint="Nothing to review right now."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-4">Applicant</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Dates</th>
                  <th className="py-2 pr-4">Days</th>
                  <th className="py-2 pr-4">Reason</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r: LeaveApplication) => {
                  const busy =
                    (approve.isPending && approve.variables?.id === r.id) ||
                    (reject.isPending && reject.variables?.id === r.id);
                  const decidable = r.status === "pending";
                  return (
                    <tr key={r.id}>
                      <td className="py-2 pr-4">
                        <div className="font-semibold text-slate-900">{r.applicant_name || "—"}</div>
                        <div className="text-xs text-slate-500">{r.applicant_email || ""}</div>
                      </td>
                      <td className="py-2 pr-4 capitalize">{r.leave_type}</td>
                      <td className="py-2 pr-4">{r.start_date} → {r.end_date}</td>
                      <td className="py-2 pr-4">{r.days}</td>
                      <td className="py-2 pr-4 text-slate-600 max-w-xs truncate" title={r.reason || ""}>
                        {r.reason || "—"}
                      </td>
                      <td className="py-2 pr-4"><StatusPill status={r.status} /></td>
                      <td className="py-2 pr-4 text-right">
                        {decidable ? (
                          <div className="inline-flex gap-2">
                            <button
                              disabled={busy}
                              onClick={() => handleDecide(r.id, "approve")}
                              className="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-2.5 py-1 rounded-md disabled:opacity-50"
                            >
                              {busy && approve.variables?.id === r.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Check className="w-3 h-3" />
                              )}
                              Approve
                            </button>
                            <button
                              disabled={busy}
                              onClick={() => handleDecide(r.id, "reject")}
                              className="inline-flex items-center gap-1 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-2.5 py-1 rounded-md disabled:opacity-50"
                            >
                              {busy && reject.variables?.id === r.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <X className="w-3 h-3" />
                              )}
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">
                            {r.approver_name ? `by ${r.approver_name}` : "—"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function EmptyState({
  icon, title, hint,
}: { icon: React.ReactNode; title: string; hint: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="mb-3">{icon}</div>
      <h3 className="text-sm font-bold text-slate-900">{title}</h3>
      <p className="text-xs text-slate-500 mt-1 max-w-sm">{hint}</p>
    </div>
  );
}
