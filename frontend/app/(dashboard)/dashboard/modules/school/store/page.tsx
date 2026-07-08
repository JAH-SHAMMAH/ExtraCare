"use client";

import { useMemo, useState } from "react";
import {
  useStoreItems, useCreateStoreItem, useDeleteStoreItem, usePurchaseStock, useAdjustStock, useAccounts,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Package, Plus, X, Loader2, Trash2, AlertTriangle, PackagePlus, PackageMinus } from "lucide-react";
import type { StoreItem } from "@/types";

export default function StorePage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");

  const { data, isLoading, isError, refetch } = useStoreItems();
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreateStoreItem();
  const del = useDeleteStoreItem();
  const purchase = usePurchaseStock();
  const adjust = useAdjustStock();

  const invAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);
  const fundAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset" || a.type === "liability"), [accounts]);

  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", sku: "", unit_price: "", cost_price: "", reorder_level: "" });
  const reset = () => { setForm({ name: "", sku: "", unit_price: "", cost_price: "", reorder_level: "" }); setShow(false); };
  const submit = () => create.mutate({
    name: form.name.trim(), sku: form.sku || null, unit_price: Number(form.unit_price) || 0,
    cost_price: Number(form.cost_price) || 0, reorder_level: Number(form.reorder_level) || 0,
  }, { onSuccess: reset });

  const [buy, setBuy] = useState<StoreItem | null>(null);
  const [buyForm, setBuyForm] = useState({ quantity: "", unit_cost: "", inventory_account_id: "", funding_account_id: "" });
  const doPurchase = () => {
    if (!buy) return;
    purchase.mutate({ id: buy.id, data: { quantity: Number(buyForm.quantity), unit_cost: Number(buyForm.unit_cost), inventory_account_id: buyForm.inventory_account_id, funding_account_id: buyForm.funding_account_id } },
      { onSuccess: () => { setBuy(null); setBuyForm({ quantity: "", unit_cost: "", inventory_account_id: "", funding_account_id: "" }); } });
  };

  const issue = (item: StoreItem) => {
    const qty = prompt(`Issue out how many "${item.name}"? (current: ${item.quantity})`);
    if (qty && Number(qty) > 0) adjust.mutate({ id: item.id, data: { type: "out", quantity: Number(qty) } });
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Store &amp; Inventory</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Store &amp; Inventory</h1>
          <p className="text-slate-500 text-sm mt-0.5">Stock items; purchases post Dr Inventory / Cr funding to the ledger.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Item</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Store Item</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2"><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">SKU</label><input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className="input" /></div>
            <div><label className="label">Sale Price</label><input type="number" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} className="input" /></div>
            <div><label className="label">Cost Price</label><input type="number" value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} className="input" /></div>
            <div><label className="label">Reorder Level</label><input type="number" value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {buy && canPost && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setBuy(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Purchase stock — {buy.name}</h3><button onClick={() => setBuy(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
            <div className="px-6 py-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div><label className="label">Quantity *</label><input type="number" value={buyForm.quantity} onChange={(e) => setBuyForm({ ...buyForm, quantity: e.target.value })} className="input" /></div>
              <div><label className="label">Unit Cost *</label><input type="number" value={buyForm.unit_cost} onChange={(e) => setBuyForm({ ...buyForm, unit_cost: e.target.value })} className="input" /></div>
              <div><label className="label">Inventory Account *</label><select value={buyForm.inventory_account_id} onChange={(e) => setBuyForm({ ...buyForm, inventory_account_id: e.target.value })} className="input"><option value="">Select…</option>{invAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
              <div><label className="label">Paid From *</label><select value={buyForm.funding_account_id} onChange={(e) => setBuyForm({ ...buyForm, funding_account_id: e.target.value })} className="input"><option value="">Select…</option>{fundAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setBuy(null)} className="btn-secondary">Cancel</button><button onClick={doPurchase} disabled={!buyForm.quantity || !buyForm.unit_cost || !buyForm.inventory_account_id || !buyForm.funding_account_id || purchase.isPending} className="btn-primary gap-2">{purchase.isPending && <Loader2 size={15} className="animate-spin" />}Purchase + post</button></div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Item", "SKU", "In stock", "Sale price", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load items.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((i) => (
                <tr key={i.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{i.name}</td>
                  <td className="px-5 py-4 text-xs font-mono text-slate-400">{i.sku || "—"}</td>
                  <td className="px-5 py-4">
                    <span className="text-sm text-slate-700">{i.quantity}</span>
                    {i.low_stock && <span className="ml-2 text-[10px] font-bold uppercase text-amber-600">low</span>}
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-600">{i.unit_price.toFixed(2)}</td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {canPost && <button onClick={() => { setBuy(i); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><PackagePlus size={13} /> Purchase</button>}
                      {canWrite && <button onClick={() => issue(i)} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100"><PackageMinus size={13} /> Issue</button>}
                      {canWrite && <button onClick={() => { if (confirm("Delete this item?")) del.mutate(i.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-16 text-center text-slate-400"><Package size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No store items yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
