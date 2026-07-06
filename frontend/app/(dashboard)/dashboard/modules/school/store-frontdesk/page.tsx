"use client";

import { useState } from "react";
import Link from "next/link";
import { useStoreItems, useStoreSales, useCreateStoreSale, useVoidStoreSale } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { ShoppingCart, Plus, Minus, X, Loader2, Trash2, Receipt, Ban, Search, Lock, Store, CheckCircle2 } from "lucide-react";
import type { StoreItem, StoreSale } from "@/types";

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

type CartLine = { item_id: string; name: string; unit_price: number; quantity: number; stock: number };

export default function StoreFrontDeskPage() {
  const canPost = useHasPermission("store:sell");
  const { data: itemsData, isLoading } = useStoreItems();
  const items: StoreItem[] = (itemsData as any)?.items ?? [];
  const { data: sales } = useStoreSales();
  const createSale = useCreateStoreSale();
  const voidSale = useVoidStoreSale();

  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [customer, setCustomer] = useState("");
  const [discount, setDiscount] = useState("");
  const [payment, setPayment] = useState("cash");
  const [receipt, setReceipt] = useState<StoreSale | null>(null);

  const filtered = items.filter((i) => i.is_active && i.name.toLowerCase().includes(search.toLowerCase()));

  const addToCart = (it: StoreItem) => {
    setCart((prev) => {
      const ex = prev.find((c) => c.item_id === it.id);
      if (ex) {
        if (ex.quantity >= it.quantity) return prev;   // don't exceed stock
        return prev.map((c) => (c.item_id === it.id ? { ...c, quantity: c.quantity + 1 } : c));
      }
      if (it.quantity < 1) return prev;
      return [...prev, { item_id: it.id, name: it.name, unit_price: it.unit_price, quantity: 1, stock: it.quantity }];
    });
  };
  const setQty = (id: string, q: number) => setCart((prev) => prev.map((c) => (c.item_id === id ? { ...c, quantity: Math.max(1, Math.min(q, c.stock)) } : c)));
  const removeLine = (id: string) => setCart((prev) => prev.filter((c) => c.item_id !== id));

  const subtotal = cart.reduce((s, c) => s + c.quantity * c.unit_price, 0);
  const disc = Math.min(Math.max(Number(discount) || 0, 0), subtotal);
  const total = subtotal - disc;
  const canCheckout = cart.length > 0 && total > 0;

  const checkout = () => {
    if (!canCheckout) return;
    createSale.mutate(
      { customer_name: customer.trim() || null, discount: disc, payment_method: payment, lines: cart.map((c) => ({ item_id: c.item_id, quantity: c.quantity })) },
      { onSuccess: (sale) => { setReceipt(sale); setCart([]); setCustomer(""); setDiscount(""); } },
    );
  };

  if (!canPost) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500">
          <Lock size={32} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold">The front desk records till sales.</p>
          <p className="text-sm mt-1">That requires the <span className="font-mono">store:sell</span> permission (the Cashier role).</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Store FrontDesk</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Store Front Desk</h1>
        <p className="text-slate-500 text-sm mt-0.5">Ring up over-the-counter sales. Each sale reduces stock and posts <span className="font-mono">Dr Cash / Cr Store Sales</span> to the ledger.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Catalog */}
        <div className="lg:col-span-2">
          <div className="relative mb-4">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} className="input pl-9" placeholder="Search store items…" />
          </div>
          {isLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
          ) : filtered.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Store size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No items in stock</p><Link href="/dashboard/modules/school/store" className="text-brand-600 hover:text-brand-700 text-sm font-semibold mt-1 inline-block">Add items in Store & Inventory →</Link></div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {filtered.map((it) => {
                const out = it.quantity < 1;
                return (
                  <button key={it.id} disabled={out} onClick={() => addToCart(it)} className={cn("text-left bg-white rounded-xl border p-4 transition", out ? "border-slate-200 opacity-50 cursor-not-allowed" : "border-slate-200 hover:border-brand-300 hover:shadow-sm")}>
                    <p className="text-sm font-bold text-slate-900 truncate">{it.name}</p>
                    <p className="text-sm text-brand-600 font-semibold mt-1">{naira(it.unit_price)}</p>
                    <p className={cn("text-[11px] mt-1", it.low_stock ? "text-amber-600" : "text-slate-400")}>{out ? "Out of stock" : `${it.quantity} in stock`}</p>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Cart */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-slate-200 p-5 sticky top-4">
            <div className="flex items-center gap-2 mb-4"><ShoppingCart size={16} className="text-brand-600" /><h2 className="text-sm font-bold text-slate-800">Cart</h2>{cart.length > 0 && <span className="text-xs text-slate-400">({cart.length})</span>}</div>
            {cart.length === 0 ? (
              <p className="text-sm text-slate-400 py-6 text-center">Tap items to add them.</p>
            ) : (
              <div className="space-y-3 mb-4">
                {cart.map((c) => (
                  <div key={c.item_id} className="flex items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-800 truncate">{c.name}</p>
                      <p className="text-[11px] text-slate-400">{naira(c.unit_price)} × {c.quantity} = {naira(c.unit_price * c.quantity)}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button onClick={() => setQty(c.item_id, c.quantity - 1)} className="w-6 h-6 rounded border border-slate-200 flex items-center justify-center text-slate-500 hover:bg-slate-50"><Minus size={12} /></button>
                      <span className="w-6 text-center text-sm tabular-nums">{c.quantity}</span>
                      <button onClick={() => setQty(c.item_id, c.quantity + 1)} disabled={c.quantity >= c.stock} className="w-6 h-6 rounded border border-slate-200 flex items-center justify-center text-slate-500 hover:bg-slate-50 disabled:opacity-40"><Plus size={12} /></button>
                      <button onClick={() => removeLine(c.item_id)} className="text-slate-400 hover:text-red-600 ml-1"><Trash2 size={13} /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-2 border-t border-slate-100 pt-3">
              <input value={customer} onChange={(e) => setCustomer(e.target.value)} className="input" placeholder="Customer (optional)" />
              <div className="grid grid-cols-2 gap-2">
                <input type="number" min="0" value={discount} onChange={(e) => setDiscount(e.target.value)} className="input" placeholder="Discount ₦" />
                <select value={payment} onChange={(e) => setPayment(e.target.value)} className="input"><option value="cash">Cash</option><option value="transfer">Transfer</option><option value="pos">POS</option></select>
              </div>
            </div>

            <div className="border-t border-slate-100 mt-3 pt-3 space-y-1 text-sm">
              <div className="flex justify-between text-slate-500"><span>Subtotal</span><span>{naira(subtotal)}</span></div>
              {disc > 0 && <div className="flex justify-between text-slate-500"><span>Discount</span><span>−{naira(disc)}</span></div>}
              <div className="flex justify-between text-base font-black text-slate-900"><span>Total</span><span>{naira(total)}</span></div>
            </div>

            <button onClick={checkout} disabled={!canCheckout || createSale.isPending} className="btn-primary w-full mt-4 gap-2 justify-center">{createSale.isPending && <Loader2 size={15} className="animate-spin" />}<Receipt size={15} /> Record sale</button>
          </div>
        </div>
      </div>

      {/* Recent sales */}
      <div className="mt-8">
        <h2 className="text-sm font-bold text-slate-800 mb-3">Recent sales</h2>
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["When", "Customer", "Items", "Total", "Payment", "Status", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {(sales ?? []).length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center text-slate-400"><Receipt size={32} className="mx-auto mb-2 opacity-40" /><p className="text-sm font-semibold">No sales yet</p></td></tr>
              ) : (
                (sales ?? []).map((s: StoreSale) => (
                  <tr key={s.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3 text-sm text-slate-600">{formatDate(s.created_at)}</td>
                    <td className="px-5 py-3 text-sm text-slate-700">{s.customer_name || "Walk-in"}</td>
                    <td className="px-5 py-3 text-sm text-slate-500">{s.lines.length}</td>
                    <td className="px-5 py-3 text-sm font-semibold text-slate-800">{naira(s.total)}</td>
                    <td className="px-5 py-3 text-sm text-slate-500 capitalize">{s.payment_method}</td>
                    <td className="px-5 py-3"><span className={cn("badge capitalize", s.status === "void" ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>{s.status}</span></td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        <button onClick={() => setReceipt(s)} className="text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50">Receipt</button>
                        {s.status === "completed" && <button onClick={() => { if (confirm("Void this sale? It reverses the ledger entry and restores stock.")) voidSale.mutate(s.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={12} /> Void</button>}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Receipt modal */}
      {receipt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={() => setReceipt(null)}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2"><CheckCircle2 size={18} className="text-emerald-600" /><h2 className="text-sm font-bold text-slate-800">Receipt</h2></div>
              <button onClick={() => setReceipt(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <p className="text-[11px] text-slate-400 mb-1">{formatDate(receipt.created_at)} · {receipt.reference || receipt.id.slice(0, 8)}</p>
            <p className="text-xs text-slate-500 mb-3">{receipt.customer_name || "Walk-in"} · <span className="capitalize">{receipt.payment_method}</span></p>
            <div className="border-y border-slate-100 py-2 space-y-1">
              {receipt.lines.map((l) => (
                <div key={l.id} className="flex justify-between text-sm"><span className="text-slate-600">{l.item_name} × {l.quantity}</span><span className="text-slate-800">{naira(l.amount)}</span></div>
              ))}
            </div>
            <div className="pt-2 space-y-1 text-sm">
              <div className="flex justify-between text-slate-500"><span>Subtotal</span><span>{naira(receipt.subtotal)}</span></div>
              {receipt.discount > 0 && <div className="flex justify-between text-slate-500"><span>Discount</span><span>−{naira(receipt.discount)}</span></div>}
              <div className="flex justify-between text-base font-black text-slate-900"><span>Total</span><span>{naira(receipt.total)}</span></div>
            </div>
            <button onClick={() => window.print()} className="btn-secondary w-full mt-4 justify-center">Print</button>
          </div>
        </div>
      )}
    </div>
  );
}
