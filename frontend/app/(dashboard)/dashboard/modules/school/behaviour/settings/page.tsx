"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useBehaviourSettings, useUpdateBehaviourSettings } from "@/hooks/useBehaviourConfig";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ArrowLeft, Loader2, Save } from "lucide-react";

function Toggle({ label, hint, checked, onChange, disabled }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void; disabled: boolean }) {
  return (
    <label className="flex items-start justify-between gap-4 py-4 border-b border-slate-100 last:border-0 cursor-pointer">
      <div>
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        <p className="text-xs text-slate-500 mt-0.5">{hint}</p>
      </div>
      <input type="checkbox" className="mt-1 h-4 w-4 shrink-0" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

export default function BehaviourSettingsPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const { data, isLoading } = useBehaviourSettings();
  const update = useUpdateBehaviourSettings();

  const [form, setForm] = useState({ default_points: 1, visible_to_students: false, visible_to_parents: false, auto_derive_levels: true });
  useEffect(() => {
    if (data) setForm({ default_points: data.default_points, visible_to_students: data.visible_to_students, visible_to_parents: data.visible_to_parents, auto_derive_levels: data.auto_derive_levels });
  }, [data]);

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <Link href="/dashboard/modules/school/behaviour" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Behaviour Tracker</Link>
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Behaviour Tracker</span><span>/</span><span className="text-brand-600 font-semibold">Settings</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">Behaviour Tracker Settings</h1>
      <p className="text-slate-500 text-sm mb-6">Org-wide defaults and visibility for behaviour records.</p>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="pb-4 border-b border-slate-100">
            <label className="label">Default points for a new record</label>
            <input type="number" value={form.default_points} disabled={!canWrite} onChange={(e) => setForm({ ...form, default_points: Number(e.target.value) })} className="input w-32" />
          </div>
          <Toggle label="Visible to students" hint="Let students see their own behaviour records." checked={form.visible_to_students} disabled={!canWrite} onChange={(v) => setForm({ ...form, visible_to_students: v })} />
          <Toggle label="Visible to parents" hint="Let guardians see their child's behaviour records." checked={form.visible_to_parents} disabled={!canWrite} onChange={(v) => setForm({ ...form, visible_to_parents: v })} />
          <Toggle label="Auto-derive behaviour levels" hint="Classify each student into a level band from their cumulative points." checked={form.auto_derive_levels} disabled={!canWrite} onChange={(v) => setForm({ ...form, auto_derive_levels: v })} />

          {canWrite && (
            <div className="flex justify-end pt-5">
              <button onClick={() => update.mutate(form)} disabled={update.isPending} className="btn-primary gap-2">{update.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}Save settings</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
