"use client";

import { useState, Fragment } from "react";
import Link from "next/link";
import {
  useRequisitions, useApproveRequisition, useRejectRequisition,
  useVoidRequisition, useDeleteRequisition,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  ClipboardList, Plus, ChevronDown, ChevronRight, Loader2, Trash2, AlertTriangle,
  CheckCircle2, Ban, XCircle, ShieldCheck,
} from "lucide-react";
import type { Requisition } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600 border-slate-200",
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-amber-50 text-amber-700 border-amber-200",
  void: "bg-rose-50 text-rose-700 border-rose-200",
};

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function RequisitionsPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [statusFilter, setStatusFilter] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: reqs, isLoading, isError, refetch } = useRequisitions(statusFilter ? { status: statusFilter } : undefined);
  const approve = useApproveRequisition();
  const reject = useRejectRequisition();
  const voidReq = useVoidRequisition();
  const del = useDeleteRequisition();

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Requisitions</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Requisitions</h1>
          <p className="text-slate-500 text-sm mt-0.5">Approve, reject and track purchase / expense requests. Approving posts the spend to the ledger.</p>
        </div>
        {canWrite && <Link href="/dashboard/modules/school/request-form" className="btn-primary gap-2"><Plus size={15} /> New Request</Link>}
      </div>

      <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} className="mt-0.5 shrink-0" />
        <span>Two-person control: a requisition can't be approved by the person who raised it. Approve posts <span className="font-mono">Dr Expense / Cr Cash·Payable</span>; approved requisitions are voided (reversed), never deleted.</span>
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {["draft", "approved", "rejected", "void"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["", "Requisition", "Dept", "Items", "Total", "Status", "Actions"].map((h) => <th key={h} className="px-4 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 7 }).map((_, j) => <td key={j} className="px-4 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={7} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load requisitions.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : reqs && reqs.length > 0 ? (
              reqs.map((r: Requisition) => (
                <Fragment key={r.id}>
                  <tr className="hover:bg-slate-50/70">
                    <td className="px-4 py-4"><button onClick={() => setExpanded(expanded === r.id ? null : r.id)} className="text-slate-400 hover:text-slate-700">{expanded === r.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</button></td>
                    <td className="px-4 py-4 text-sm font-medium text-slate-800">{r.title}{r.category && <span className="block text-[11px] text-slate-400 capitalize">{r.category}</span>}<span className="block text-[11px] text-slate-400">{formatDate(r.created_at)}</span></td>
                    <td className="px-4 py-4 text-sm text-slate-600">{r.department || "—"}</td>
                    <td className="px-4 py-4 text-sm text-slate-600">{r.items.length}</td>
                    <td className="px-4 py-4 text-sm font-semibold text-slate-800">{naira(r.total_amount)}</td>
                    <td className="px-4 py-4"><span className={cn("badge capitalize", STATUS_STYLE[r.status] || "")}>{r.status}</span></td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-1">
                        {r.status === "draft" && canPost && <button onClick={() => { if (confirm(`Approve & post "${r.title}"? This writes ${naira(r.total_amount)} to the ledger.`)) approve.mutate(r.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><CheckCircle2 size={13} /> Approve</button>}
                        {r.status === "draft" && canPost && <button onClick={() => { if (confirm(`Reject "${r.title}"?`)) reject.mutate(r.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 px-2 py-1 rounded hover:bg-amber-50"><XCircle size={13} /> Reject</button>}
                        {r.status === "approved" && canPost && <button onClick={() => { if (confirm(`Void "${r.title}"? This reverses the ledger entry.`)) voidReq.mutate(r.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Void</button>}
                        {(r.status === "draft" || r.status === "rejected") && canWrite && <button onClick={() => { if (confirm("Delete this requisition?")) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                      </div>
                    </td>
                  </tr>
                  {expanded === r.id && (
                    <tr className="bg-slate-50/40">
                      <td />
                      <td colSpan={6} className="px-4 py-3">
                        <div className="text-xs text-slate-500 mb-2">{r.justification && <p className="mb-2"><span className="font-semibold text-slate-600">Justification:</span> {r.justification}</p>}</div>
                        <div className="rounded-lg border border-slate-200 bg-white">
                          <div className="grid grid-cols-12 gap-2 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 border-b border-slate-100">
                            <div className="col-span-6">Item</div><div className="col-span-2">Qty</div><div className="col-span-2">Unit</div><div className="col-span-2">Amount</div>
                          </div>
                          {r.items.map((it) => (
                            <div key={it.id} className="grid grid-cols-12 gap-2 px-3 py-2 text-sm border-b border-slate-50 last:border-0">
                              <div className="col-span-6 text-slate-700">{it.description}{it.note && <span className="block text-[11px] text-slate-400">{it.note}</span>}</div>
                              <div className="col-span-2 text-slate-600">{it.quantity}</div>
                              <div className="col-span-2 text-slate-600">{naira(it.unit_cost)}</div>
                              <div className="col-span-2 font-medium text-slate-800">{naira(it.amount)}</div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            ) : (
              <tr><td colSpan={7} className="py-16 text-center text-slate-400"><ClipboardList size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No requisitions yet</p><Link href="/dashboard/modules/school/request-form" className="text-brand-600 hover:text-brand-700 text-sm font-semibold mt-1 inline-block">Raise one via the Request Form →</Link></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
