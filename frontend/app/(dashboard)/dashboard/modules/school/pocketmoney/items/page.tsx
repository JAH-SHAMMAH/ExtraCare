"use client";

import { useState } from "react";
import { usePocketMoneyItems, useCreatePMItem, useUpdatePMItem, useDeletePMItem } from "@/hooks/useWallet";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatCurrency } from "@/lib/utils";
import { ShoppingCart, Plus, Loader2, AlertTriangle, Trash2, Lock } from "lucide-react";
import type { PocketMoneyItem } from "@/types";

export default function PocketMoneyItemsPage() {
  const canWrite = useHasPermission("payments:write");
  const { data: items, isLoading, isError, refetch } = usePocketMoneyItems(false);
  const create = useCreatePMItem();
  const update = useUpdatePMItem();
  const remove = useDeletePMItem();

  const [form, setForm] = useState({ name: "", unit_price: "" });
  const add = () => create.mutate({ name: form.name.trim(), unit_price: Number(form.unit_price || 0), is_active: true },
    { onSuccess: () => setForm({ name: "", unit_price: "" }) });

  const rows: PocketMoneyItem[] = items ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>PocketMoney Manager</span><span>/</span><span className="text-brand-600 font-semibold">PocketMoney Items</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">PocketMoney Items</h1>
        <p className="text-slate-500 text-sm mt-0.5">The purchasable canteen / tuck-shop catalogue used when recording a New Transaction.</p>
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 flex flex-col sm:flex-row gap-3 sm:items-end">
          <div className="flex-1"><label className="label">Item name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. Meat Pie" /></div>
          <div className="w-40"><label className="label">Unit price *</label><input type="number" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} className="input" placeholder="0.00" /></div>
          <button onClick={add} disabled={!form.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Add item</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Item", "Unit Price", "Status", canWrite ? "Actions" : ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 4 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={4} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load items.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows.length > 0 ? (
              rows.map((it) => <ItemRow key={it.id} item={it} canWrite={canWrite} onToggle={(v) => update.mutate({ id: it.id, data: { is_active: v } })} onDelete={() => remove.mutate(it.id)} onPrice={(p) => update.mutate({ id: it.id, data: { unit_price: p } })} />)
            ) : (
              <tr><td colSpan={4} className="py-16 text-center text-slate-400"><ShoppingCart size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No items yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Managing the catalogue requires payments write access.</p>}
    </div>
  );
}

function ItemRow({ item, canWrite, onToggle, onDelete, onPrice }: { item: PocketMoneyItem; canWrite: boolean; onToggle: (v: boolean) => void; onDelete: () => void; onPrice: (p: number) => void }) {
  return (
    <tr className="hover:bg-slate-50/70">
      <td className="px-5 py-4 text-sm font-medium text-slate-800">{item.name}</td>
      <td className="px-5 py-4 text-sm text-slate-700">
        {canWrite ? (
          <input type="number" defaultValue={item.unit_price} onBlur={(e) => { const v = Number(e.target.value); if (v !== item.unit_price) onPrice(v); }} className="input py-1 text-xs w-28" />
        ) : formatCurrency(item.unit_price)}
      </td>
      <td className="px-5 py-4">
        <button disabled={!canWrite} onClick={() => onToggle(!item.is_active)} className={cn("badge", item.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200", canWrite && "cursor-pointer")}>{item.is_active ? "Active" : "Inactive"}</button>
      </td>
      <td className="px-5 py-4">{canWrite && <button onClick={onDelete} className="text-rose-500 hover:text-rose-700 p-1.5 rounded hover:bg-rose-50"><Trash2 size={15} /></button>}</td>
    </tr>
  );
}
