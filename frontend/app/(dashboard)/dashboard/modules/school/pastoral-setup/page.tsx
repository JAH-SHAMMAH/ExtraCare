"use client";

import { useEffect, useState } from "react";
import { usePastoralSettings, useUpdatePastoralSettings } from "@/hooks/usePastoral";
import { useAvailableRoles } from "@/hooks/useUsers";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { HouseSetup } from "@/components/pastoral/HouseSetup";
import { HostelSetup } from "@/components/pastoral/HostelSetup";
import { PointSystemSetup, AwardSystemSetup } from "@/components/pastoral/PointAwardSetup";
import { cn } from "@/lib/utils";
import { Loader2, Save, Settings2 } from "lucide-react";

// Full Educare tab set. Functional in Batch A: Exeat Settings + Default Settings.
// The rest arrive in later batches of the Pastoral build-out (B–F).
type Tab =
  | "hostel" | "disciplinary" | "leadership" | "heads" | "house"
  | "exeat" | "report" | "rollcall" | "points" | "awards" | "default";

const TABS: [Tab, string][] = [
  ["hostel", "Hostel Setup"], ["disciplinary", "Disciplinary Setup"], ["leadership", "Leadership Roles"],
  ["heads", "Pastoral Heads"], ["house", "Pastoral House Setup"], ["exeat", "Exeat Settings"],
  ["report", "Pastoral Report Setup"], ["rollcall", "Pastoral Roll Call"], ["points", "Point System Setup"],
  ["awards", "Award System Setup"], ["default", "Default Settings"],
];

const EXEAT_FLAGS: [string, string][] = [
  ["enable_head_only_approval", "Enable Head Only Approval"],
  ["notify_parent_on_exeat_approval", "Notify Parent on Exeat Approval"],
  ["notify_house_parent_on_exeat_approval", "Notify House Parent on Exeat Approval"],
  ["notify_pastoral_head_on_new_request", "Notify Pastoral Head on New Request"],
];

const DEFAULT_FLAGS: [string, string][] = [
  ["enable_tutorial_week", "Enable Tutorial Week"],
  ["email_parent_on_new_point_entry", "Email Parent on New Point Entry"],
  ["enable_academic_cohesion", "Enable Academic Cohesion"],
  ["show_award_in_point_analysis", "Show Award in Point Analysis"],
  ["allow_referral_in_mentor_comment", "Allow Referral in Mentor Comment"],
  ["enable_point_category", "Enable Point Category"],
  ["enable_mentor_report_assessment", "Enable Mentor Report Assessment"],
  ["allow_only_merits_in_point_entry", "Allow Only Merits in Point Entry"],
  ["allow_observation_in_mentor_comment", "Allow Observation in Mentor Comment"],
];

export default function PastoralSetupPage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [tab, setTab] = useState<Tab>("exeat");
  const { data: settings, isLoading, isError, refetch } = usePastoralSettings();
  const { data: rolesData } = useAvailableRoles();
  const update = useUpdatePastoralSettings();

  const [form, setForm] = useState<any>(null);
  useEffect(() => { if (settings && !form) setForm(settings); }, [settings, form]);

  const set = (k: string, v: any) => setForm((p: any) => ({ ...p, [k]: v }));
  const save = () => form && update.mutate(form);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Pastoral Setup</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><Settings2 size={22} className="text-brand-600" /> Pastoral Setup</h1>
      <p className="text-slate-500 text-sm mb-5">Configuration for the Pastoral & Boarding module.</p>

      <div className="flex gap-1 border-b border-slate-200 mb-6 overflow-x-auto">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-3.5 py-2 text-sm font-semibold border-b-2 -mb-px transition whitespace-nowrap", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>

      {/* Placeholder tabs are STATIC — never gated on the settings fetch, so they
          render instantly even if /pastoral/settings is slow or failing. Only the
          two settings-backed tabs depend on the query. */}
      {tab === "house" ? (
        <HouseSetup canWrite={canWrite} />
      ) : tab === "hostel" ? (
        <HostelSetup canWrite={canWrite} />
      ) : tab === "points" ? (
        <PointSystemSetup canWrite={canWrite} />
      ) : tab === "awards" ? (
        <AwardSystemSetup canWrite={canWrite} />
      ) : tab !== "exeat" && tab !== "default" ? (
        <Placeholder label={TABS.find(([k]) => k === tab)?.[1] ?? ""} />
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <p className="text-sm font-semibold text-slate-600">Couldn&apos;t load pastoral settings.</p>
          <p className="text-xs text-slate-400 mt-1">If this persists, the backend may be pending migration <code>100_pastoral_settings</code>.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : !form ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : tab === "exeat" ? (
        <SettingsCard title="Exeat Settings" flags={EXEAT_FLAGS} form={form} set={set} canWrite={canWrite} onSave={save} saving={update.isPending} />
      ) : tab === "default" ? (
        <SettingsCard
          title="Default Settings" flags={DEFAULT_FLAGS} form={form} set={set} canWrite={canWrite} onSave={save} saving={update.isPending}
          extra={
            <div className="pt-2">
              <label className="label">School Nurse Role</label>
              <select
                value={form.school_nurse_role_id ?? ""} disabled={!canWrite}
                onChange={(e) => set("school_nurse_role_id", e.target.value)}
                className="input max-w-xs"
              >
                <option value="">— None —</option>
                {(rolesData?.items ?? []).map((r: any) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
          }
        />
      ) : null}
    </div>
  );
}

function SettingsCard({
  title, flags, form, set, canWrite, onSave, saving, extra,
}: {
  title: string; flags: [string, string][]; form: any; set: (k: string, v: any) => void;
  canWrite: boolean; onSave: () => void; saving: boolean; extra?: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 max-w-2xl">
      <h2 className="text-sm font-bold text-slate-800 mb-4">{title}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
        {flags.map(([key, label]) => (
          <label key={key} className={cn("flex items-center gap-2.5 text-sm", canWrite ? "text-slate-700 cursor-pointer" : "text-slate-500")}>
            <input type="checkbox" checked={!!form[key]} disabled={!canWrite} onChange={(e) => set(key, e.target.checked)} className="w-4 h-4 rounded" />
            {label}
          </label>
        ))}
      </div>
      {extra}
      {canWrite && (
        <div className="mt-5 pt-4 border-t border-slate-100">
          <button onClick={onSave} disabled={saving} className="btn-primary gap-2">{saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Submit</button>
        </div>
      )}
    </div>
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <div className="bg-white rounded-xl border border-dashed border-slate-200 p-12 text-center">
      <Settings2 size={30} className="mx-auto mb-3 text-slate-300" />
      <p className="text-sm font-semibold text-slate-600">{label}</p>
      <p className="text-xs text-slate-400 mt-1">Arrives in an upcoming batch of the Pastoral build-out.</p>
    </div>
  );
}
