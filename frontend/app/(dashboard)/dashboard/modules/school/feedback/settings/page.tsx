"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useFeedbackSettings, useUpdateFeedbackSettings } from "@/hooks/useFeedbackExtras";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ArrowLeft, Loader2, Save } from "lucide-react";

function Toggle({ label, hint, checked, onChange, disabled }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void; disabled: boolean }) {
  return (
    <label className="flex items-start justify-between gap-4 py-4 border-b border-slate-100 last:border-0 cursor-pointer">
      <div><p className="text-sm font-semibold text-slate-800">{label}</p><p className="text-xs text-slate-500 mt-0.5">{hint}</p></div>
      <input type="checkbox" className="mt-1 h-4 w-4 shrink-0" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

export default function FeedbackSettingsPage() {
  const canWrite = useHasPermission("school:feedback:write");
  const { data, isLoading } = useFeedbackSettings();
  const update = useUpdateFeedbackSettings();

  const [form, setForm] = useState({ allow_anonymous: true, notify_on_submit: false, acknowledgement_message: "" });
  useEffect(() => {
    if (data) setForm({ allow_anonymous: data.allow_anonymous, notify_on_submit: data.notify_on_submit, acknowledgement_message: data.acknowledgement_message || "" });
  }, [data]);

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">Settings</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">Feedback Settings</h1>
      <p className="text-slate-500 text-sm mb-6">Configure the feedback channel for your school.</p>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <Toggle label="Allow anonymous submissions" hint="Let submitters hide their identity from reviewers." checked={form.allow_anonymous} disabled={!canWrite} onChange={(v) => setForm({ ...form, allow_anonymous: v })} />
          <Toggle label="Notify admins on submit" hint="Flag new feedback for staff attention." checked={form.notify_on_submit} disabled={!canWrite} onChange={(v) => setForm({ ...form, notify_on_submit: v })} />
          <div className="py-4">
            <label className="label">Acknowledgement message</label>
            <textarea value={form.acknowledgement_message} disabled={!canWrite} onChange={(e) => setForm({ ...form, acknowledgement_message: e.target.value })} className="input" rows={3} placeholder="Shown on the feedback form, e.g. “Thanks — we review feedback weekly.”" />
          </div>
          {canWrite && (
            <div className="flex justify-end">
              <button onClick={() => update.mutate({ ...form, acknowledgement_message: form.acknowledgement_message || null })} disabled={update.isPending} className="btn-primary gap-2">{update.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}Save settings</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
