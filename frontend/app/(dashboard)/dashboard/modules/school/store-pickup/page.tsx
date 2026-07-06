"use client";

import { useState } from "react";
import Link from "next/link";
import {
  usePickupPoints, usePickups, useCreatePickupPoint, useDeletePickupPoint,
  useCreatePickup, useCollectPickup, useCancelPickup, useDeletePickup,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { MapPin, Plus, X, Loader2, Trash2, AlertTriangle, PackageCheck, PackageX, Package, Clock } from "lucide-react";
import type { PickupPoint, Pickup } from "@/types";

type StatusFilter = "all" | "pending" | "collected" | "cancelled";

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  collected: "bg-emerald-50 text-emerald-700 border-emerald-200",
  cancelled: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function StorePickupPage() {
  const canWrite = useHasPermission("payments:write");   // manage points + tickets
  const canSell = useHasPermission("store:sell");        // cashier
  const canCollect = canWrite || canSell;                // marking collected = either
  const { data: points, isLoading: pointsLoading } = usePickupPoints();

  const [pointFilter, setPointFilter] = useState<string | null>(null);   // null = all points
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending");
  const params = {
    ...(statusFilter !== "all" ? { status: statusFilter } : {}),
    ...(pointFilter ? { pickup_point_id: pointFilter } : {}),
  };
  const { data: pickups, isLoading, isError, refetch } = usePickups(params);

  const createPoint = useCreatePickupPoint();
  const delPoint = useDeletePickupPoint();
  const createTicket = useCreatePickup();
  const collect = useCollectPickup();
  const cancel = useCancelPickup();
  const delTicket = useDeletePickup();

  const [showPoint, setShowPoint] = useState(false);
  const [pointForm, setPointForm] = useState({ name: "", location: "", notes: "" });
  const resetPoint = () => { setPointForm({ name: "", location: "", notes: "" }); setShowPoint(false); };
  const submitPoint = () => {
    if (!pointForm.name.trim()) return;
    createPoint.mutate(
      { name: pointForm.name.trim(), location: pointForm.location.trim() || null, notes: pointForm.notes.trim() || null },
      { onSuccess: resetPoint },
    );
  };

  const [showTicket, setShowTicket] = useState(false);
  const [ticket, setTicket] = useState({ pickup_point_id: "", customer_name: "", description: "", reference: "", notes: "" });
  const resetTicket = () => { setTicket({ pickup_point_id: "", customer_name: "", description: "", reference: "", notes: "" }); setShowTicket(false); };
  const submitTicket = () => {
    if (!ticket.description.trim()) return;
    createTicket.mutate(
      {
        pickup_point_id: ticket.pickup_point_id || null,
        customer_name: ticket.customer_name.trim() || null,
        description: ticket.description.trim(),
        reference: ticket.reference.trim() || null,
        notes: ticket.notes.trim() || null,
      },
      { onSuccess: resetTicket },
    );
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Store Pickup</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Store Pickup Unit</h1>
          <p className="text-slate-500 text-sm mt-0.5">Track where students collect items bought from the <Link href="/dashboard/modules/school/store" className="text-brand-600 hover:text-brand-700 font-semibold">Store</Link>, and mark each collection done.</p>
        </div>
        {canWrite && <button onClick={() => { resetTicket(); setShowTicket(true); }} className="btn-primary gap-2"><Plus size={15} /> New Pickup</button>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pickup points */}
        <div className="lg:col-span-1 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Pickup points</h2>
            {canWrite && <button onClick={() => { resetPoint(); setShowPoint(true); }} className="text-brand-600 hover:text-brand-700 text-xs font-semibold flex items-center gap-1"><Plus size={13} /> Add</button>}
          </div>

          <button onClick={() => setPointFilter(null)} className={cn("w-full text-left bg-white rounded-xl border p-3 transition", pointFilter === null ? "border-brand-300 ring-1 ring-brand-100" : "border-slate-200 hover:border-slate-300")}>
            <p className="text-sm font-bold text-slate-800">All points</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Show pickups from every point</p>
          </button>

          {pointsLoading ? (
            Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)
          ) : (points ?? []).length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 py-10 text-center text-slate-400"><MapPin size={26} className="mx-auto mb-2 opacity-40" /><p className="font-semibold text-xs">No pickup points yet</p></div>
          ) : (
            (points ?? []).map((p) => (
              <button key={p.id} onClick={() => setPointFilter(p.id)} className={cn("w-full text-left bg-white rounded-xl border p-4 transition", pointFilter === p.id ? "border-brand-300 ring-1 ring-brand-100" : "border-slate-200 hover:border-slate-300")}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{p.name}{!p.is_active && <span className="ml-1 text-[10px] text-slate-400">(inactive)</span>}</p>
                    {p.location && <p className="text-[11px] text-slate-400 flex items-center gap-1"><MapPin size={10} /> {p.location}</p>}
                  </div>
                  {canWrite && <button onClick={(e) => { e.stopPropagation(); if (confirm("Remove this pickup point? (must have no pending pickups)")) delPoint.mutate(p.id); }} className="text-slate-400 hover:text-red-600 shrink-0"><Trash2 size={13} /></button>}
                </div>
                {p.pending_count > 0
                  ? <p className="text-[11px] text-amber-600 font-semibold mt-2 flex items-center gap-1"><Clock size={11} /> {p.pending_count} pending</p>
                  : <p className="text-[11px] text-slate-400 mt-2">No pending pickups</p>}
              </button>
            ))
          )}
        </div>

        {/* Pickups list */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-1.5 mb-3 flex-wrap">
            {(["pending", "collected", "cancelled", "all"] as StatusFilter[]).map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)} className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition", statusFilter === s ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300")}>{s}</button>
            ))}
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            {isLoading ? (
              <div className="p-5 space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-10 bg-slate-100 rounded animate-pulse" />)}</div>
            ) : isError ? (
              <div className="py-14 text-center"><AlertTriangle size={24} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary text-xs">Retry</button></div>
            ) : (pickups ?? []).length === 0 ? (
              <div className="py-16 text-center text-slate-400"><Package size={36} className="mx-auto mb-3 opacity-30" /><p className="font-semibold text-sm">No {statusFilter !== "all" ? statusFilter : ""} pickups</p>{canWrite && <p className="text-xs mt-1">Create one with <b>New Pickup</b>.</p>}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Item / description", "Customer", "Point", "Ref", "Status", ""].map((h) => <th key={h} className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-slate-50">
                    {(pickups ?? []).map((pk) => (
                      <tr key={pk.id} className="hover:bg-slate-50/70 align-top">
                        <td className="px-4 py-3 text-sm font-medium text-slate-800">{pk.description}</td>
                        <td className="px-4 py-3 text-sm text-slate-600">{pk.customer_name || "—"}</td>
                        <td className="px-4 py-3 text-sm text-slate-500">{pk.pickup_point_name || "—"}</td>
                        <td className="px-4 py-3 text-sm text-slate-400">{pk.reference || "—"}</td>
                        <td className="px-4 py-3"><span className={cn("badge capitalize", STATUS_BADGE[pk.status])}>{pk.status}</span></td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 justify-end">
                            {pk.status === "pending" && (
                              <>
                                {canCollect && <button onClick={() => collect.mutate(pk.id)} disabled={collect.isPending} title="Mark collected" className="text-emerald-600 hover:text-emerald-700"><PackageCheck size={16} /></button>}
                                {canWrite && <button onClick={() => cancel.mutate(pk.id)} disabled={cancel.isPending} title="Cancel" className="text-slate-400 hover:text-amber-600"><PackageX size={16} /></button>}
                              </>
                            )}
                            {canWrite && pk.status !== "pending" && (
                              <button onClick={() => { if (confirm("Delete this pickup record?")) delTicket.mutate(pk.id); }} title="Delete" className="text-slate-400 hover:text-red-600"><Trash2 size={14} /></button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* New pickup point modal */}
      {showPoint && canWrite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={resetPoint}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New pickup point</h2><button onClick={resetPoint} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="space-y-3">
              <div><label className="label">Name *</label><input value={pointForm.name} onChange={(e) => setPointForm({ ...pointForm, name: e.target.value })} className="input" placeholder="e.g. Front Desk" /></div>
              <div><label className="label">Location</label><input value={pointForm.location} onChange={(e) => setPointForm({ ...pointForm, location: e.target.value })} className="input" placeholder="Building / room" /></div>
              <div><label className="label">Notes</label><input value={pointForm.notes} onChange={(e) => setPointForm({ ...pointForm, notes: e.target.value })} className="input" placeholder="optional" /></div>
            </div>
            <div className="flex justify-end gap-3 mt-5"><button onClick={resetPoint} className="btn-secondary">Cancel</button><button onClick={submitPoint} disabled={!pointForm.name.trim() || createPoint.isPending} className="btn-primary gap-2">{createPoint.isPending && <Loader2 size={15} className="animate-spin" />}Add point</button></div>
          </div>
        </div>
      )}

      {/* New pickup ticket modal */}
      {showTicket && canWrite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={resetTicket}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New pickup</h2><button onClick={resetTicket} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="space-y-3">
              <div><label className="label">What to collect *</label><input value={ticket.description} onChange={(e) => setTicket({ ...ticket, description: e.target.value })} className="input" placeholder="e.g. 1x School bag, 2x Notebook" /></div>
              <div><label className="label">Customer / student name</label><input value={ticket.customer_name} onChange={(e) => setTicket({ ...ticket, customer_name: e.target.value })} className="input" placeholder="Who collects it" /></div>
              <div>
                <label className="label">Pickup point</label>
                <select value={ticket.pickup_point_id} onChange={(e) => setTicket({ ...ticket, pickup_point_id: e.target.value })} className="input">
                  <option value="">No specific point</option>
                  {(points ?? []).filter((p) => p.is_active).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div><label className="label">Reference</label><input value={ticket.reference} onChange={(e) => setTicket({ ...ticket, reference: e.target.value })} className="input" placeholder="Sale / receipt no. (optional)" /></div>
              <div><label className="label">Notes</label><input value={ticket.notes} onChange={(e) => setTicket({ ...ticket, notes: e.target.value })} className="input" placeholder="optional" /></div>
            </div>
            <div className="flex justify-end gap-3 mt-5"><button onClick={resetTicket} className="btn-secondary">Cancel</button><button onClick={submitTicket} disabled={!ticket.description.trim() || createTicket.isPending} className="btn-primary gap-2">{createTicket.isPending && <Loader2 size={15} className="animate-spin" />}Create pickup</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
