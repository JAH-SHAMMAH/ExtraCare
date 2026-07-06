"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "@/lib/store";
import { supportApi } from "@/lib/api";
import { LifeBuoy, Mail, Send, CheckCircle2, Loader2 } from "lucide-react";

const SUPPORT_EMAIL = "shammahbadman@gmail.com";

export default function SupportPage() {
  const { user, org } = useAuthStore();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);

  const buildMailto = () => {
    const body = [
      message,
      "",
      "—",
      `From: ${user?.full_name || ""} <${user?.email || ""}>`,
      org?.name ? `School: ${org.name}` : "",
    ].filter(Boolean).join("\n");
    const params = new URLSearchParams({ subject: subject || "Support request", body });
    return `mailto:${SUPPORT_EMAIL}?${params.toString()}`;
  };

  // Server-side: persists the request and emails support. If the request fails,
  // fall back to the user's mail client so the message is never lost.
  const send = useMutation({
    mutationFn: () => supportApi.send({ subject: subject.trim(), message: message.trim() }),
    onSuccess: () => { setSent(true); toast.success("Message sent to support."); },
    onError: () => { window.location.href = buildMailto(); setSent(true); },
  });

  const submit = () => {
    if (!subject.trim() || !message.trim()) return;
    send.mutate();
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Core</span><span>/</span><span className="text-brand-600 font-semibold">Support</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><LifeBuoy size={22} className="text-brand-600" /> Support</h1>
        <p className="text-slate-500 text-sm mt-0.5">Need help? Send us a message — it goes straight to our team.</p>
      </div>

      {/* Direct email — always works */}
      <a href={`mailto:${SUPPORT_EMAIL}`} className="flex items-center gap-3 bg-brand-50 border border-brand-200 rounded-xl px-5 py-4 mb-6 hover:bg-brand-100/60 transition-colors">
        <div className="w-10 h-10 rounded-lg bg-brand-600 flex items-center justify-center text-white shrink-0"><Mail size={18} /></div>
        <div>
          <p className="text-sm font-bold text-slate-800">Email us directly</p>
          <p className="text-sm text-brand-700 font-semibold">{SUPPORT_EMAIL}</p>
        </div>
      </a>

      {/* Contact form */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-sm font-bold text-slate-800 mb-4">Send a message</h2>
        {sent ? (
          <div className="py-8 text-center">
            <CheckCircle2 size={40} className="mx-auto mb-3 text-emerald-500" />
            <p className="font-semibold text-slate-800">Your mail client is opening…</p>
            <p className="text-sm text-slate-500 mt-1">If nothing happened, email us at <a href={`mailto:${SUPPORT_EMAIL}`} className="text-brand-600 font-semibold">{SUPPORT_EMAIL}</a>.</p>
            <button onClick={() => { setSent(false); setSubject(""); setMessage(""); }} className="mt-4 btn-secondary">Send another</button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div><label className="label">Your name</label><input value={user?.full_name || ""} readOnly className="input bg-slate-50" /></div>
              <div><label className="label">Your email</label><input value={user?.email || ""} readOnly className="input bg-slate-50" /></div>
            </div>
            <div className="mb-4"><label className="label">Subject *</label><input value={subject} onChange={(e) => setSubject(e.target.value)} className="input" placeholder="What do you need help with?" /></div>
            <div className="mb-4"><label className="label">Message *</label><textarea value={message} onChange={(e) => setMessage(e.target.value)} className="input min-h-[140px]" placeholder="Describe the issue or question…" /></div>
            <div className="flex justify-end">
              <button onClick={submit} disabled={!subject.trim() || !message.trim() || send.isPending} className="btn-primary gap-2">{send.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Send message</button>
            </div>
          </>
        )}
      </div>

      <p className="text-xs text-slate-400 mt-4">We typically respond within one business day.</p>
    </div>
  );
}
