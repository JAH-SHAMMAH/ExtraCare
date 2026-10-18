"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function StoreAppointmentsPage() {
  const qc = useQueryClient();
  const [f, setF] = useState({ purpose: "", appt_date: "", appt_time: "", phone: "" });
  const list = useQuery({ queryKey: ["parent-appts"], queryFn: () => api.get("/office/parent/store-appointments").then((r) => r.data as { items: any[] }) });
  const book = useMutation({
    mutationFn: () => api.post("/office/parent/store-appointments", f).then((r) => r.data),
    onSuccess: () => { toast.success("Appointment booked."); setF({ purpose: "", appt_date: "", appt_time: "", phone: "" }); qc.invalidateQueries({ queryKey: ["parent-appts"] }); },
    onError: (e: any) => toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not book."),
  });
  return (
    <div className="p-4 sm:p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-4">Store Appointments</h1>
      <form onSubmit={(e) => { e.preventDefault(); book.mutate(); }} className="bg-slate-50 border border-slate-200 rounded-xl p-4 grid sm:grid-cols-2 gap-3 mb-6">
        <label className="text-sm font-semibold">Date<input type="date" required className="input mt-1" value={f.appt_date} onChange={(e) => setF({ ...f, appt_date: e.target.value })} /></label>
        <label className="text-sm font-semibold">Time<input type="time" required className="input mt-1" value={f.appt_time} onChange={(e) => setF({ ...f, appt_time: e.target.value })} /></label>
        <label className="text-sm font-semibold sm:col-span-2">What do you need to buy or collect?<input className="input mt-1" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} /></label>
        <label className="text-sm font-semibold sm:col-span-2">Phone<input className="input mt-1" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></label>
        <button className="btn-primary sm:col-span-2" disabled={book.isPending}>Book appointment</button>
      </form>
      {list.isLoading ? <Loader2 className="animate-spin text-slate-400 mx-auto" /> : (
        <ul className="space-y-2">
          {(list.data?.items ?? []).map((a) => <li key={a.id} className="bg-white border border-slate-200 rounded-lg p-3 text-sm flex justify-between"><span>{a.appt_date} {a.appt_time} · {a.purpose}</span><b>{a.status}</b></li>)}
          {!list.data?.items.length && <li className="text-slate-400 text-sm">No appointments yet.</li>}
        </ul>
      )}
    </div>
  );
}
