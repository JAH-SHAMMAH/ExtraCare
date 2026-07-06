"use client";

import { useEffect, useMemo, useState } from "react";
import {
  useInvoices, useCreateInvoice, useDeleteInvoice, usePostInvoice, usePayInvoice, useVoidInvoice,
  useAccounts, useFinanceSettings,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { PrintLetterhead } from "@/components/branding/Brand";
import { cn, formatDate } from "@/lib/utils";
import { Receipt, Plus, X, Loader2, Trash2, AlertTriangle, CheckCircle2, Ban, Banknote, Printer } from "lucide-react";
import type { FinanceInvoice } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-50 text-slate-500 border-slate-200",
  posted: "bg-blue-50 text-blue-700 border-blue-200",
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  void: "bg-rose-50 text-rose-700 border-rose-200",
};

type LineDraft = { description: string; quantity: string; unit_price: string; income_account_id: string };

export default function InvoicesPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [statusFilter, setStatusFilter] = useState("");
  const [show, setShow] = useState(false);

  const { data, isLoading, isError, refetch } = useInvoices(statusFilter ? { status: statusFilter } : undefined);
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreateInvoice();
  const del = useDeleteInvoice();
  const post = usePostInvoice();
  const pay = usePayInvoice();
  const voidInv = useVoidInvoice();

  const assetAccounts = useMemo(() => (accounts ?? []).filter((a) => a.type === "asset"), [accounts]);
  const incomeAccounts = useMemo(() => (accounts ?? []).filter((a) => a.type === "income"), [accounts]);

  const { data: defaults } = useFinanceSettings();
  const [form, setForm] = useState({ customer_name: "", student_id: "", invoice_date: "", due_date: "", receivable_account_id: "", memo: "" });
  const [lines, setLines] = useState<LineDraft[]>([{ description: "", quantity: "1", unit_price: "", income_account_id: "" }]);

  const reset = () => {
    setForm({ customer_name: "", student_id: "", invoice_date: "", due_date: "", receivable_account_id: defaults?.default_receivable_account_id || "", memo: "" });
    setLines([{ description: "", quantity: "1", unit_price: "", income_account_id: defaults?.default_income_account_id || "" }]);
    setShow(false);
  };
  // Pre-fill Accounts Setup defaults on load where empty (receivable + each line's
  // income account); reset() and new lines re-seed. Never override a manual pick.
  useEffect(() => {
    if (!defaults) return;
    setForm((f) => ({ ...f, receivable_account_id: f.receivable_account_id || defaults.default_receivable_account_id || "" }));
    setLines((ls) => ls.map((l) => ({ ...l, income_account_id: l.income_account_id || defaults.default_income_account_id || "" })));
  }, [defaults]);
  const submit = () => {
    const cleaned = lines.filter((l) => l.description.trim() && l.income_account_id).map((l) => ({
      description: l.description.trim(), quantity: Number(l.quantity) || 1, unit_price: Number(l.unit_price) || 0, income_account_id: l.income_account_id,
    }));
    if (cleaned.length === 0) return;
    create.mutate({
      customer_name: form.customer_name.trim(), student_id: form.student_id || null,
      invoice_date: form.invoice_date || null, due_date: form.due_date || null,
      receivable_account_id: form.receivable_account_id, memo: form.memo || null, lines: cleaned,
    }, { onSuccess: reset });
  };

  const doPay = (id: string) => {
    const cashId = assetAccounts[0]?.id;
    const chosen = prompt(`Cash account id to receive into:\n${assetAccounts.map((a) => `${a.code} ${a.name} → ${a.id}`).join("\n")}`, cashId || "");
    if (chosen) pay.mutate({ id, data: { cash_account_id: chosen.trim() } });
  };

  // Branded invoice document → browser print / Save-as-PDF. Render the chosen
  // invoice into the print-only document, then trigger print; clear afterwards.
  const [printInvoice, setPrintInvoice] = useState<FinanceInvoice | null>(null);
  useEffect(() => {
    if (!printInvoice) return;
    const clear = () => setPrintInvoice(null);
    window.addEventListener("afterprint", clear);
    window.print();
    return () => window.removeEventListener("afterprint", clear);
  }, [printInvoice]);

  const rows = data?.items;

  return (
    <>
    <div className="p-8 max-w-6xl mx-auto no-print">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Invoice Center</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Invoice Center</h1>
          <p className="text-slate-500 text-sm mt-0.5">Draft invoices, then post them to the ledger. {canPost ? "" : "Posting is restricted to accountants/admins."}</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Invoice</button>}
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize"><option value="">All statuses</option>{["draft", "posted", "paid", "void"].map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Invoice (draft)</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div><label className="label">Customer *</label><input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} className="input" /></div>
            <div><label className="label">Student (optional)</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Receivable Account *</label><select value={form.receivable_account_id} onChange={(e) => setForm({ ...form, receivable_account_id: e.target.value })} className="input"><option value="">Select…</option>{assetAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
            <div><label className="label">Invoice Date</label><input type="date" value={form.invoice_date} onChange={(e) => setForm({ ...form, invoice_date: e.target.value })} className="input" /></div>
            <div><label className="label">Due Date</label><input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="input" /></div>
            <div><label className="label">Memo</label><input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} className="input" /></div>
          </div>
          <label className="label">Lines</label>
          <div className="space-y-2 mb-3">
            {lines.map((l, i) => (
              <div key={i} className="grid grid-cols-12 gap-2">
                <input value={l.description} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} className="input col-span-4" placeholder="Description" />
                <input type="number" value={l.quantity} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, quantity: e.target.value } : x))} className="input col-span-1" placeholder="Qty" />
                <input type="number" value={l.unit_price} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, unit_price: e.target.value } : x))} className="input col-span-2" placeholder="Unit price" />
                <select value={l.income_account_id} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, income_account_id: e.target.value } : x))} className="input col-span-4"><option value="">Income account…</option>{incomeAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select>
                <button onClick={() => setLines(lines.filter((_, j) => j !== i))} className="col-span-1 text-slate-400 hover:text-red-600"><X size={15} /></button>
              </div>
            ))}
          </div>
          <button onClick={() => setLines([...lines, { description: "", quantity: "1", unit_price: "", income_account_id: defaults?.default_income_account_id || "" }])} className="text-xs font-semibold text-brand-600 hover:text-brand-700 mb-4">+ Add line</button>
          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.customer_name.trim() || !form.receivable_account_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Save draft</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Number", "Customer", "Total", "Status", "Date", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load invoices.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((inv) => (
                <tr key={inv.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-mono text-slate-600">{inv.number}</td>
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{inv.customer_name}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{inv.total.toFixed(2)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[inv.status] || "")}>{inv.status}</span></td>
                  <td className="px-5 py-4 text-xs text-slate-500">{inv.invoice_date ? formatDate(inv.invoice_date) : "—"}</td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      <button onClick={() => setPrintInvoice(inv)} title="Print / save as PDF" className="text-slate-400 hover:text-brand-600 p-1"><Printer size={14} /></button>
                      {inv.status === "draft" && canPost && <button onClick={() => post.mutate(inv.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 px-2 py-1 rounded hover:bg-blue-50"><CheckCircle2 size={13} /> Post</button>}
                      {inv.status === "draft" && canWrite && <button onClick={() => { if (confirm("Delete draft?")) del.mutate(inv.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                      {inv.status === "posted" && canPost && <button onClick={() => doPay(inv.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><Banknote size={13} /> Pay</button>}
                      {(inv.status === "posted" || inv.status === "paid") && canPost && <button onClick={() => { if (confirm("Void this invoice? Its ledger entries will be reversed.")) voidInv.mutate(inv.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Void</button>}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><Receipt size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No invoices yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
    <PrintableInvoice invoice={printInvoice} />
    </>
  );
}

/** Print-only branded invoice document (crest letterhead + lines). Hidden on
 *  screen; shown only when printing / saving as PDF. */
function PrintableInvoice({ invoice }: { invoice: FinanceInvoice | null }) {
  if (!invoice) return null;
  return (
    <div className="print-only p-2 text-slate-900">
      <PrintLetterhead title="Invoice" subtitle={invoice.number} />
      <div className="flex justify-between mb-6 text-sm">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Billed to</p>
          <p className="font-semibold">{invoice.customer_name}</p>
        </div>
        <div className="text-right">
          <p><span className="text-slate-400">Invoice no: </span>{invoice.number}</p>
          <p><span className="text-slate-400">Date: </span>{invoice.invoice_date ? formatDate(invoice.invoice_date) : "—"}</p>
          {invoice.due_date && <p><span className="text-slate-400">Due: </span>{formatDate(invoice.due_date)}</p>}
          <p className="capitalize"><span className="text-slate-400">Status: </span>{invoice.status}</p>
        </div>
      </div>
      <table className="w-full text-left text-sm mb-6">
        <thead><tr className="border-b-2 border-slate-300">{["Description", "Qty", "Unit price", "Amount"].map((h) => <th key={h} className="py-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
        <tbody>
          {(invoice.lines ?? []).map((l, i) => (
            <tr key={i} className="border-b border-slate-100">
              <td className="py-2">{l.description}</td>
              <td className="py-2">{l.quantity}</td>
              <td className="py-2">{Number(l.unit_price).toFixed(2)}</td>
              <td className="py-2">{Number(l.amount).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex justify-end">
        <div className="w-56 flex justify-between border-t-2 border-slate-300 pt-2">
          <span className="text-sm font-bold uppercase tracking-wide text-slate-500">Total</span>
          <span className="text-lg font-black">{invoice.total.toFixed(2)}</span>
        </div>
      </div>
      {invoice.memo && <p className="mt-6 text-xs text-slate-500">{invoice.memo}</p>}
    </div>
  );
}
