"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";

const money = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function BillsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["parent-bills"], queryFn: () => api.get("/office/parent/bills").then((r) => r.data as { children: any[] }) });
  if (isLoading) return <Loader2 className="animate-spin text-slate-400 mx-auto my-16" />;
  return (
    <div className="p-4 sm:p-8 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Bills &amp; Stores</h1>
      {!data?.children.length && <p className="text-slate-400">No children found on your account.</p>}
      {data?.children.map((c) => (
        <section key={c.id} className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="font-bold text-lg mb-2">{c.name}</h2>
          <h3 className="text-xs uppercase text-slate-500 mb-1">Fee invoices</h3>
          {c.invoices.length ? c.invoices.map((i: any) => (
            <div key={i.number} className="flex justify-between text-sm py-1 border-t first:border-t-0"><span>{i.number} · {i.date ?? ""}</span><span>{money(i.total)} <em className="text-slate-500 not-italic">({i.status})</em></span></div>
          )) : <p className="text-sm text-slate-400">No invoices.</p>}
          <h3 className="text-xs uppercase text-slate-500 mt-3 mb-1">Store &amp; tuckshop</h3>
          {c.store.length ? c.store.map((s: any, k: number) => (
            <div key={k} className="flex justify-between text-sm py-1 border-t first:border-t-0"><span>{s.reference} · {s.date ?? ""}</span><span>{money(s.total)}</span></div>
          )) : <p className="text-sm text-slate-400">No purchases.</p>}
        </section>
      ))}
    </div>
  );
}
