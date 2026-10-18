"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Loader2, ShieldAlert, Save } from "lucide-react";
import { toast } from "sonner";
import { useAuthStore } from "@/lib/store";
import { isSuperUser } from "@/lib/superFlags";
import { useSuperSettings, useSaveSuperSettings, useSuperStruct } from "@/hooks/useSuperSettings";
import type { SuperField } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ChecklistTab } from "@/components/super/ChecklistTab";
import { DocCategoriesTab } from "@/components/super/DocCategoriesTab";
import { PatternTab } from "@/components/super/PatternTab";
import { NotificationsTab } from "@/components/super/NotificationsTab";
import { RolePermsTab } from "@/components/super/RolePermsTab";
import { ModuleAccessTab } from "@/components/super/ModuleAccessTab";

const GENERAL_TABS = ["General", "Themes", "Module Manager", "Module Permissions Manager", "User Role Permissions", "Notifications", "Other Settings"];
const SUB_TABS = [
  "School Settings", "School Information", "Module Re-order", "Password Reset Manager", "Payment Security",
  "Reg. Number Pattern", "Staff ID Pattern", "Email Pattern", "Student Email Pattern", "Student Documents",
  "Entrance Exam Subject", "Full Name Format and Order", "Student Dashboard Settings", "Teacher Dashboard Settings",
];

// Tabs that are managed on pages the app already has.
const LINKS: Record<string, { href: string; text: string; cta: string }> = {
  "Themes": { href: "/dashboard/settings", text: "School colours, logo and look are set under Settings.", cta: "Open Settings" },
  "Module Manager": { href: "/dashboard/billing", text: "Which modules the school uses follows its plan.", cta: "Open Plan & Billing" },
  "Other Settings": { href: "/dashboard/settings", text: "Backups, profile and the rest of the organisation settings.", cta: "Open Settings" },
};

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={cn("relative inline-flex h-8 w-20 items-center rounded-md border text-xs font-bold text-white transition-colors",
        on ? "bg-emerald-500 border-emerald-600 justify-start pl-3" : "bg-red-600 border-red-700 justify-end pr-3")}>
      {on ? "On" : "Off"}
      <span className={cn("absolute top-0.5 h-6 w-5 rounded bg-white", on ? "right-0.5" : "left-0.5")} />
    </button>
  );
}

function FieldRow({ f, value, onChange }: { f: SuperField; value: any; onChange: (v: any) => void }) {
  return (
    <div className="py-3 border-b border-slate-100 last:border-0">
      <label className="block text-xs font-bold uppercase tracking-wide text-slate-600 mb-1.5">{f.label}</label>
      {f.kind === "bool" ? (
        <Toggle on={!!value} onChange={onChange} label={f.label} />
      ) : f.kind.startsWith("select:") ? (
        <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          {f.kind.split(":")[1].split("|").map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
        </select>
      ) : f.kind === "number" ? (
        <input type="number" min={0} className="input" value={value ?? 0} onChange={(e) => onChange(Number(e.target.value))} />
      ) : (
        <input type={f.kind === "password" ? "password" : "text"} autoComplete="off" className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      )}
      {f.help && <p className="text-xs text-slate-400 mt-1">{f.help}</p>}
    </div>
  );
}

export default function SuperSettingsPage() {
  const user = useAuthStore((s) => s.user);
  const allowed = isSuperUser(user as any);
  const { data, isLoading } = useSuperSettings(allowed);
  const save = useSaveSuperSettings();
  const struct = useSuperStruct(allowed);
  const sv = struct.data?.values; const meta = struct.data?.meta;
  const [general, setGeneral] = useState("General");
  const [sub, setSub] = useState("School Settings");
  const [edits, setEdits] = useState<Record<string, any>>({});

  const fields = data?.fields ?? [];
  const values = { ...(data?.values ?? {}), ...edits };
  const shown = useMemo(() => fields.filter((f) => f.tab === sub), [fields, sub]);
  const sections = useMemo(() => {
    const m = new Map<string, SuperField[]>();
    shown.forEach((f) => m.set(f.section, [...(m.get(f.section) ?? []), f]));
    return [...m.entries()];
  }, [shown]);
  const dirty = Object.keys(edits).length > 0;

  if (!allowed) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-400 px-8">
        <ShieldAlert size={44} className="mb-4 opacity-40" />
        <p className="font-semibold text-slate-700 text-lg">Super User only</p>
        <p className="text-sm mt-1 text-center max-w-md">These settings can only be changed by the school&apos;s Super User.</p>
      </div>
    );
  }

  const onSave = () => save.mutate(edits, {
    onSuccess: () => { setEdits({}); toast.success("Settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Could not save settings."),
  });

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Super Settings</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">Only the Super User sees this. Each switch opens or closes the pages and actions it controls.</p>

      <div className="flex flex-wrap gap-x-5 gap-y-1 border-b border-slate-200 mb-3">
        {GENERAL_TABS.map((t) => (
          <button key={t} onClick={() => setGeneral(t)} className={cn("py-2 text-xs font-bold uppercase tracking-wide border-b-2 -mb-px", general === t ? "border-emerald-500 text-emerald-600" : "border-transparent text-slate-600 hover:text-slate-900")}>{t}</button>
        ))}
      </div>

      {general === "Module Permissions Manager" ? <ModuleAccessTab server={sv?.module_access} />
      : general === "User Role Permissions" ? <RolePermsTab server={sv?.role_perms} items={meta?.role_perm_items ?? []} />
      : general === "Notifications" ? <NotificationsTab server={sv?.notification_prefs} events={meta?.notification_events ?? []} />
      : general !== "General" ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6 text-sm text-slate-600">
          <p>{LINKS[general]?.text}</p>
          {LINKS[general] && <Link href={LINKS[general].href} className="btn-primary inline-flex mt-4">{LINKS[general].cta}</Link>}
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-x-4 gap-y-1 border-b border-slate-200 mb-4">
            {SUB_TABS.map((t) => (
              <button key={t} onClick={() => setSub(t)} className={cn("py-2 text-sm font-semibold border-b-2 -mb-px", sub === t ? "border-emerald-500 text-emerald-600" : "border-transparent text-slate-600 hover:text-slate-900")}>{t}</button>
            ))}
          </div>
          {sub === "Student Dashboard Settings" ? <ChecklistTab title="Student Dashboard Settings" structKey="student_dashboard" items={meta?.student_dashboard_items ?? []} server={sv?.student_dashboard} />
          : sub === "Teacher Dashboard Settings" ? <ChecklistTab title="Teacher Dashboard Settings" structKey="teacher_dashboard" items={meta?.teacher_dashboard_items ?? []} server={sv?.teacher_dashboard} />
          : sub === "Student Documents" ? <DocCategoriesTab server={sv?.doc_categories} />
          : sub === "Reg. Number Pattern" ? <PatternTab title="Reg. Number Pattern" patternKey="reg_number" server={sv?.patterns} />
          : sub === "Staff ID Pattern" ? <PatternTab title="Staff ID Pattern" patternKey="staff_id" server={sv?.patterns} />
          : sub === "Email Pattern" ? <PatternTab title="Email Pattern" patternKey="email" server={sv?.patterns} lower />
          : sub === "Student Email Pattern" ? <PatternTab title="Student Email Pattern" patternKey="student_email" server={sv?.patterns} lower />
          : isLoading ? (
            <div className="py-16 text-center"><Loader2 className="animate-spin text-slate-400 mx-auto" /></div>
          ) : (
            <div className="space-y-4">
              {sections.map(([title, fs]) => (
                <div key={title} className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6">
                  {sections.length > 1 && <h2 className="text-sm font-bold text-slate-800 mb-1">{title}</h2>}
                  {fs.map((f) => (
                    <FieldRow key={f.key} f={f} value={values[f.key]}
                      onChange={(v) => setEdits((e) => (v === data?.values?.[f.key] ? Object.fromEntries(Object.entries(e).filter(([k]) => k !== f.key)) : { ...e, [f.key]: v }))} />
                  ))}
                </div>
              ))}
              <button onClick={onSave} disabled={!dirty || save.isPending} className="btn-primary gap-2">
                {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Change
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
