"use client";

import { useState } from "react";
import { useSentMessages, useInbox, useSendMessage, useMarkRead } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { MessageSquare, Send, Loader2, Mail, MailOpen, X } from "lucide-react";

type Tab = "inbox" | "compose" | "sent";

export default function MailboxPage() {
  const canSend = useHasPermission("settings:write");
  const [tab, setTab] = useState<Tab>("inbox");
  const { data: inbox } = useInbox();
  const unread = (inbox ?? []).filter((i: any) => !i.read_at).length;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">Mailbox</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Mailbox</h1>
        <p className="text-slate-500 text-sm mt-0.5">Internal announcements & memos with read receipts.</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["inbox", `Inbox${unread ? ` (${unread})` : ""}`], ...(canSend ? [["compose", "Compose"], ["sent", "Sent"]] as [Tab, string][] : [])] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {tab === "inbox" ? <Inbox /> : tab === "compose" ? <Compose onSent={() => setTab("sent")} /> : <Sent />}
    </div>
  );
}

function Inbox() {
  const { data, isLoading } = useInbox();
  const markRead = useMarkRead();
  const [open, setOpen] = useState<string | null>(null);
  if (isLoading) return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>;
  if ((data ?? []).length === 0) return <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Mail size={36} className="mb-3 opacity-40" /><p className="font-semibold">Your inbox is empty</p></div>;
  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
      {data!.map((m: any) => (
        <div key={m.recipient_row_id}>
          <button onClick={() => { setOpen(open === m.recipient_row_id ? null : m.recipient_row_id); if (!m.read_at) markRead.mutate(m.recipient_row_id); }} className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-slate-50/70">
            {m.read_at ? <MailOpen size={16} className="text-slate-300" /> : <Mail size={16} className="text-brand-600" />}
            <span className={cn("text-sm flex-1", m.read_at ? "text-slate-600" : "font-bold text-slate-900")}>{m.subject}</span>
            <span className="text-xs text-slate-400">{formatDate(m.created_at)}</span>
          </button>
          {open === m.recipient_row_id && <div className="px-12 pb-4 text-sm text-slate-600 whitespace-pre-wrap">{m.body || <span className="text-slate-400 italic">No content.</span>}</div>}
        </div>
      ))}
    </div>
  );
}

function Compose({ onSent }: { onSent: () => void }) {
  const send = useSendMessage();
  const [f, setF] = useState({ subject: "", body: "", all_staff: false });
  const [recipients, setRecipients] = useState<{ id: string; name: string }[]>([]);
  const [picker, setPicker] = useState<string | null>(null);

  const submit = () => send.mutate(
    { subject: f.subject.trim(), body: f.body || null, all_staff: f.all_staff, recipient_ids: recipients.map((r) => r.id) },
    { onSuccess: () => { setF({ subject: "", body: "", all_staff: false }); setRecipients([]); onSent(); } }
  );

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
      <div><label className="label">Subject *</label><input value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} className="input" /></div>
      <div><label className="label">Message</label><textarea value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} className="input min-h-[120px]" /></div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.all_staff} onChange={(e) => setF({ ...f, all_staff: e.target.checked })} /> Send to all active staff</label>
      {!f.all_staff && (
        <div>
          <label className="label">Recipients</label>
          <div className="flex flex-wrap gap-2 mb-2">{recipients.map((r) => <span key={r.id} className="inline-flex items-center gap-1 bg-slate-100 rounded-full pl-3 pr-1.5 py-1 text-xs font-medium text-slate-700">{r.name}<button onClick={() => setRecipients(recipients.filter((x) => x.id !== r.id))} className="text-slate-400 hover:text-red-600"><X size={12} /></button></span>)}</div>
          <EntityPicker type="staff" value={picker} onChange={(id, label) => { if (id && !recipients.find((r) => r.id === id)) setRecipients([...recipients, { id, name: label || id.slice(0, 6) }]); setPicker(null); }} />
        </div>
      )}
      <div className="flex justify-end"><button onClick={submit} disabled={!f.subject.trim() || (!f.all_staff && recipients.length === 0) || send.isPending} className="btn-primary gap-2">{send.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}Send</button></div>
    </div>
  );
}

function Sent() {
  const { data, isLoading } = useSentMessages();
  if (isLoading) return <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>;
  if ((data ?? []).length === 0) return <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Send size={36} className="mb-3 opacity-40" /><p className="font-semibold">Nothing sent yet</p></div>;
  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
      {data!.map((m) => (
        <div key={m.id} className="flex items-center gap-3 px-5 py-3.5">
          <MessageSquare size={16} className="text-slate-300" />
          <span className="text-sm font-medium text-slate-800 flex-1">{m.subject}</span>
          <span className="text-xs text-slate-500">{m.read_count}/{m.recipient_count} read</span>
          <span className="text-xs text-slate-400 ml-3">{formatDate(m.created_at)}</span>
        </div>
      ))}
    </div>
  );
}
