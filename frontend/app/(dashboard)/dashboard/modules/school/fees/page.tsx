"use client";

import { useState } from "react";
import { useFees, useCreateFee, useRecordFeePayment } from "@/hooks/useSchool";
import { cn, formatDate, formatCurrency } from "@/lib/utils";
import { Wallet, Plus, X, Loader2, Search, DollarSign } from "lucide-react";
import type { FeeRecord } from "@/types";

const STATUS_MAP: Record<string, string> = { paid: "bg-emerald-50 text-emerald-700 border-emerald-200", partial: "bg-amber-50 text-amber-700 border-amber-200", unpaid: "bg-red-50 text-red-700 border-red-200", overdue: "bg-red-100 text-red-800 border-red-300" };

export default function FeesPage() {
  const [tab, setTab] = useState<"all" | "paid" | "unpaid" | "overdue">("all");
  const [showForm, setShowForm] = useState(false);
  const [payingId, setPayingId] = useState<string | null>(null);
  const [payAmount, setPayAmount] = useState("");

  const { data, isLoading } = useFees({ status: tab === "all" ? undefined : tab });
  const createFee = useCreateFee();
  const recordPayment = useRecordFeePayment();

  const [form, setForm] = useState({ student_id: "", fee_type: "tuition", amount: "", due_date: "", term: "1st Term", academic_year: new Date().getFullYear().toString() });
  const resetForm = () => { setForm({ student_id: "", fee_type: "tuition", amount: "", due_date: "", term: "1st Term", academic_year: new Date().getFullYear().toString() }); setShowForm(false); };
  const handleSubmit = () => { createFee.mutate({ ...form, amount: parseFloat(form.amount) }, { onSuccess: resetForm }); };
  const handlePay = (id: string) => { recordPayment.mutate({ id, data: { amount: parseFloat(payAmount) } }, { onSuccess: () => { setPayingId(null); setPayAmount(""); } }); };

  const items = data?.items || (Array.isArray(data) ? data : []);
  const totalCollected = items.reduce((s: number, f: FeeRecord) => s + (f.paid_amount || 0), 0);
  const totalOutstanding = items.reduce((s: number, f: FeeRecord) => s + (f.balance || 0), 0);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Fees</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Fee Management</h1>
          <p className="text-slate-500 text-sm mt-0.5">Track fees, payments, and outstanding balances.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Create Fee</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[{ label: "Total Records", value: items.length || "—" }, { label: "Collected", value: formatCurrency(totalCollected) }, { label: "Outstanding", value: formatCurrency(totalOutstanding) }, { label: "Overdue", value: items.filter((f: FeeRecord) => f.status === "overdue").length || "0" }].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4"><p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p><p className="text-xl font-black text-slate-900">{value}</p></div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Create Fee Record</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Student ID *</label><input value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} className="input" /></div>
            <div><label className="label">Fee Type</label><select value={form.fee_type} onChange={(e) => setForm({ ...form, fee_type: e.target.value })} className="input"><option value="tuition">Tuition</option><option value="admission">Admission</option><option value="exam">Exam</option><option value="transport">Transport</option><option value="hostel">Hostel</option><option value="other">Other</option></select></div>
            <div><label className="label">Amount *</label><input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="input" /></div>
            <div><label className="label">Due Date *</label><input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="input" /></div>
            <div><label className="label">Term</label><input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input" /></div>
            <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={resetForm} className="btn-secondary">Cancel</button><button onClick={handleSubmit} disabled={createFee.isPending} className="btn-primary gap-2">{createFee.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        {(["all", "paid", "unpaid", "overdue"] as const).map((t) => (<button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize", tab === t ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50")}>{t}</button>))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Type", "Amount", "Paid", "Balance", "Due Date", "Status", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => (<tr key={i}><td colSpan={8} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : items.length === 0 ? (<tr><td colSpan={8} className="px-5 py-16 text-center text-slate-400 text-sm"><Wallet size={32} className="mx-auto mb-2 opacity-50" />No fee records found.</td></tr>)
            : items.map((f: FeeRecord) => (
              <tr key={f.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="px-5 py-3.5 text-sm font-bold text-slate-900">{f.student_name || f.student_id}</td>
                <td className="px-5 py-3.5"><span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{f.fee_type}</span></td>
                <td className="px-5 py-3.5 text-sm font-medium text-slate-800">{formatCurrency(f.amount)}</td>
                <td className="px-5 py-3.5 text-sm text-emerald-600">{formatCurrency(f.paid_amount)}</td>
                <td className="px-5 py-3.5 text-sm text-red-600 font-medium">{formatCurrency(f.balance)}</td>
                <td className="px-5 py-3.5 text-xs text-slate-500">{formatDate(f.due_date)}</td>
                <td className="px-5 py-3.5"><span className={cn("badge capitalize", STATUS_MAP[f.status] || "")}>{f.status}</span></td>
                <td className="px-5 py-3.5">
                  {f.balance > 0 && (payingId === f.id ? (
                    <div className="flex items-center gap-2">
                      <input type="number" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} placeholder="Amount" className="input w-24 text-xs" />
                      <button onClick={() => handlePay(f.id)} disabled={recordPayment.isPending} className="text-xs text-brand-600 font-semibold">Pay</button>
                      <button onClick={() => setPayingId(null)} className="text-xs text-slate-400">Cancel</button>
                    </div>
                  ) : (
                    <button onClick={() => { setPayingId(f.id); setPayAmount(""); }} className="text-xs text-brand-600 font-semibold hover:underline flex items-center gap-1"><DollarSign size={12} />Record Payment</button>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
