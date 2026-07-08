"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useWarehouses, useWarehouseStock, useCreateWarehouse, useDeleteWarehouse,
  useReceiveStock, useTransferStock, useIssueStock, useStoreItems,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Warehouse as WhIcon, Plus, X, Loader2, Trash2, AlertTriangle, PackagePlus, ArrowLeftRight, PackageMinus, MapPin } from "lucide-react";
import type { Warehouse, StoreItem } from "@/types";

type ActionType = "receive" | "issue" | "transfer";

export default function WarehousePage() {
  const canWrite = useHasPermission("payments:write");
  const { data: warehouses, isLoading, isError, refetch } = useWarehouses();
  const { data: itemsData } = useStoreItems();
  const items: StoreItem[] = (itemsData as any)?.items ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = (warehouses ?? []).find((w) => w.id === selectedId) ?? null;
  const { data: stock, isLoading: stockLoading } = useWarehouseStock(selectedId);

  const create = useCreateWarehouse();
  const del = useDeleteWarehouse();
  const receive = useReceiveStock();
  const transfer = useTransferStock();
  const issue = useIssueStock();

  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", location: "", notes: "" });
  const resetNew = () => { setForm({ name: "", location: "", notes: "" }); setShowNew(false); };

  const [action, setAction] = useState<ActionType | null>(null);
  const [act, setAct] = useState({ item_id: "", quantity: "", to_warehouse_id: "" });
  const openAction = (t: ActionType) => { setAct({ item_id: "", quantity: "", to_warehouse_id: "" }); setAction(t); };
  const closeAction = () => { setAction(null); setAct({ item_id: "", quantity: "", to_warehouse_id: "" }); };

  const submitNew = () => {
    if (!form.name.trim()) return;
    create.mutate({ name: form.name.trim(), location: form.location.trim() || null, notes: form.notes.trim() || null }, {
      onSuccess: (w: Warehouse) => { resetNew(); setSelectedId(w.id); },
    });
  };

  const actionPending = receive.isPending || transfer.isPending || issue.isPending;
  const actCanSubmit = act.item_id && Number(act.quantity) > 0 && (action !== "transfer" || act.to_warehouse_id);
  const submitAction = () => {
    if (!selected || !actCanSubmit) return;
    const q = Number(act.quantity);
    if (action === "receive") receive.mutate({ warehouse_id: selected.id, item_id: act.item_id, quantity: q }, { onSuccess: closeAction });
    else if (action === "issue") issue.mutate({ warehouse_id: selected.id, item_id: act.item_id, quantity: q }, { onSuccess: closeAction });
    else transfer.mutate({ from_warehouse_id: selected.id, to_warehouse_id: act.to_warehouse_id, item_id: act.item_id, quantity: q }, { onSuccess: closeAction });
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Warehouse</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Warehouse</h1>
          <p className="text-slate-500 text-sm mt-0.5">Track bulk stock across storage locations and transfer between them. (Separate from the sellable <Link href="/dashboard/modules/school/store" className="text-brand-600 hover:text-brand-700 font-semibold">Store</Link> quantity.)</p>
        </div>
        {canWrite && <button onClick={() => { resetNew(); setShowNew(true); }} className="btn-primary gap-2"><Plus size={15} /> New Warehouse</button>}
      </div>

      {showNew && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New warehouse</h2><button onClick={resetNew} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Main Store" /></div>
            <div><label className="label">Location</label><input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="input" placeholder="Building / room" /></div>
            <div><label className="label">Notes</label><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" placeholder="optional" /></div>
          </div>
          <div className="flex justify-end gap-3"><button onClick={resetNew} className="btn-secondary">Cancel</button><button onClick={submitNew} disabled={!form.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Add warehouse</button></div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Warehouse list */}
        <div className="lg:col-span-1 space-y-3">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)
          ) : isError ? (
            <div className="bg-white rounded-xl border border-slate-200 py-10 text-center"><AlertTriangle size={24} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary text-xs mt-1">Retry</button></div>
          ) : (warehouses ?? []).length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 py-14 text-center text-slate-400"><WhIcon size={32} className="mx-auto mb-2 opacity-40" /><p className="font-semibold text-sm">No warehouses yet</p></div>
          ) : (
            (warehouses ?? []).map((w) => (
              <button key={w.id} onClick={() => setSelectedId(w.id)} className={cn("w-full text-left bg-white rounded-xl border p-4 transition", selectedId === w.id ? "border-brand-300 ring-1 ring-brand-100" : "border-slate-200 hover:border-slate-300")}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{w.name}{!w.is_active && <span className="ml-1 text-[10px] text-slate-400">(inactive)</span>}</p>
                    {w.location && <p className="text-[11px] text-slate-400 flex items-center gap-1"><MapPin size={10} /> {w.location}</p>}
                  </div>
                  {canWrite && <button onClick={(e) => { e.stopPropagation(); if (confirm("Remove this warehouse? (must be empty)")) del.mutate(w.id); }} className="text-slate-400 hover:text-red-600 shrink-0"><Trash2 size={13} /></button>}
                </div>
                <p className="text-[11px] text-slate-500 mt-2">{w.item_count} item{w.item_count === 1 ? "" : "s"} · {w.total_units} unit{w.total_units === 1 ? "" : "s"}</p>
              </button>
            ))
          )}
        </div>

        {/* Selected warehouse stock */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="bg-white rounded-xl border border-slate-200 py-20 text-center text-slate-400"><WhIcon size={40} className="mx-auto mb-3 opacity-30" /><p className="font-semibold">Select a warehouse to view its stock</p></div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between flex-wrap gap-3">
                <div><p className="text-sm font-bold text-slate-800">{selected.name}</p>{selected.location && <p className="text-[11px] text-slate-400">{selected.location}</p>}</div>
                {canWrite && (
                  <div className="flex items-center gap-2">
                    <button onClick={() => openAction("receive")} className="btn-secondary text-xs gap-1"><PackagePlus size={13} /> Receive</button>
                    <button onClick={() => openAction("transfer")} className="btn-secondary text-xs gap-1"><ArrowLeftRight size={13} /> Transfer</button>
                    <button onClick={() => openAction("issue")} className="btn-secondary text-xs gap-1"><PackageMinus size={13} /> Issue</button>
                  </div>
                )}
              </div>
              {stockLoading ? (
                <div className="p-5 space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-8 bg-slate-100 rounded animate-pulse" />)}</div>
              ) : (stock ?? []).length === 0 ? (
                <div className="py-14 text-center text-slate-400"><p className="text-sm font-semibold">This warehouse is empty</p><p className="text-xs mt-1">Use <b>Receive</b> to bring stock in.</p></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Item", "SKU", "On hand", "Reorder", ""].map((h) => <th key={h} className="px-5 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
                    <tbody className="divide-y divide-slate-50">
                      {(stock ?? []).map((r) => (
                        <tr key={r.item_id} className="hover:bg-slate-50/70">
                          <td className="px-5 py-3 text-sm font-medium text-slate-800">{r.item_name}</td>
                          <td className="px-5 py-3 text-sm text-slate-400">{r.sku || "—"}</td>
                          <td className="px-5 py-3 text-sm font-semibold text-slate-800 tabular-nums">{r.quantity}</td>
                          <td className="px-5 py-3 text-sm text-slate-500 tabular-nums">{r.reorder_level || "—"}</td>
                          <td className="px-5 py-3">{r.low_stock && <span className="badge bg-amber-50 text-amber-700 border-amber-200">Low</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Action modal */}
      {action && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={closeAction}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-800 capitalize">{action === "receive" ? "Receive stock into" : action === "issue" ? "Issue stock from" : "Transfer stock from"} {selected.name}</h2>
              <button onClick={closeAction} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="label">Item *</label>
                <select value={act.item_id} onChange={(e) => setAct({ ...act, item_id: e.target.value })} className="input">
                  <option value="">Select item…</option>
                  {items.map((it) => <option key={it.id} value={it.id}>{it.name}{it.sku ? ` (${it.sku})` : ""}</option>)}
                </select>
                {items.length === 0 && <p className="text-[11px] text-amber-600 mt-1">No store items yet — add them in Store & Inventory.</p>}
              </div>
              {action === "transfer" && (
                <div>
                  <label className="label">To warehouse *</label>
                  <select value={act.to_warehouse_id} onChange={(e) => setAct({ ...act, to_warehouse_id: e.target.value })} className="input">
                    <option value="">Select destination…</option>
                    {(warehouses ?? []).filter((w) => w.id !== selected.id).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                  </select>
                </div>
              )}
              <div><label className="label">Quantity *</label><input type="number" min="0" value={act.quantity} onChange={(e) => setAct({ ...act, quantity: e.target.value })} className="input" placeholder="0" /></div>
            </div>
            <div className="flex justify-end gap-3 mt-5"><button onClick={closeAction} className="btn-secondary">Cancel</button><button onClick={submitAction} disabled={!actCanSubmit || actionPending} className="btn-primary gap-2">{actionPending && <Loader2 size={15} className="animate-spin" />}Confirm</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
