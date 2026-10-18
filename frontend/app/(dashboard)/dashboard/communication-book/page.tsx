"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function CommunicationBookPage() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState("");
  const [sid, setSid] = useState("");
  const [reply, setReply] = useState<Record<string, string>>({});
  const bills = useQuery({ queryKey: ["parent-bills"], queryFn: () => api.get("/office/parent/bills").then((r) => r.data as { children: any[] }) });
  const list = useQuery({ queryKey: ["commbook-mine"], queryFn: () => api.get("/office/commbook/mine").then((r) => r.data as { items: any[] }) });
  const kids = bills.data?.children ?? [];
  const target = sid || kids[0]?.id || "";
  const refresh = () => qc.invalidateQueries({ queryKey: ["commbook-mine"] });
  const send = useMutation({
    mutationFn: () => api.post("/office/commbook/mine", { student_id: target, message: msg }).then((r) => r.data),
    onSuccess: () => { toast.success("Sent."); setMsg(""); refresh(); },
    onError: (e: any) => toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not send."),
  });
  const ack = useMutation({
    mutationFn: (id: string) => api.put(`/office/commbook/mine/${id}/ack`, { reply: reply[id] ?? "" }).then((r) => r.data),
    onSuccess: refresh,
    onError: () => toast.error("Could not save."),
  });
  return (
    <div className="p-4 sm:p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-4">Communication Book</h1>
      <form onSubmit={(e) => { e.preventDefault(); if (msg.trim()) send.mutate(); }} className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6 space-y-2">
        {kids.length > 1 && (
          <select className="input" aria-label="Child" value={target} onChange={(e) => setSid(e.target.value)}>
            {kids.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
        )}
        <textarea className="input" rows={3} placeholder="Write a note to the teacher" value={msg} onChange={(e) => setMsg(e.target.value)} />
        <button className="btn-primary" disabled={send.isPending || !target}>Send</button>
      </form>
      {list.isLoading ? <Loader2 className="animate-spin text-slate-400 mx-auto" /> : (
        <ul className="space-y-3">
          {(list.data?.items ?? []).map((e) => (
            <li key={e.id} className="bg-white border border-slate-200 rounded-xl p-3 text-sm">
              <div className="text-xs text-slate-500 mb-1">{e.entry_date} · {e.student_id_name} · {e.direction === "school_to_home" ? "From school" : "From home"} · {e.author}</div>
              <p>{e.message}</p>
              {e.reply && <p className="mt-1 text-slate-600">Reply: {e.reply}</p>}
              {e.direction === "school_to_home" && !e.acknowledged && (
                <div className="mt-2 flex gap-2">
                  <input className="input" placeholder="Reply (optional)" value={reply[e.id] ?? ""} onChange={(ev) => setReply((o) => ({ ...o, [e.id]: ev.target.value }))} />
                  <button onClick={() => ack.mutate(e.id)} className="btn-secondary whitespace-nowrap">Acknowledge</button>
                </div>
              )}
              {e.acknowledged && <span className="text-xs text-emerald-600 font-semibold">Acknowledged</span>}
            </li>
          ))}
          {!list.data?.items.length && <li className="text-slate-400 text-sm">Nothing here yet.</li>}
        </ul>
      )}
    </div>
  );
}
