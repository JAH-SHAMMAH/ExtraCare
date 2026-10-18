"use client";

import { useMemo, useState } from "react";
import { CORE_NAV, MODULE_SECTIONS } from "@/components/layout/Sidebar";
import { useAvailableRoles } from "@/hooks/useUsers";
import { Panel, Check, SaveBar, useStructEditor } from "@/components/super/shared";
import { roleList } from "@/components/super/RolePermsTab";

type Group = { key: string; label: string; items: { href: string; label: string }[] };

export function moduleGroups(): Group[] {
  const core = { key: "core", label: "Core", items: CORE_NAV.map((i: any) => ({ href: i.href, label: i.label })) };
  const mods = MODULE_SECTIONS.map((s: any) => ({ key: s.key, label: s.label, items: s.items.map((i: any) => ({ href: i.href, label: i.label })) }));
  return [core, ...mods];
}

export function ModuleAccessTab({ server }: { server: Record<string, string[]> | undefined }) {
  const { data } = useAvailableRoles();
  const roles = roleList(data);
  const [slug, setSlug] = useState("");
  const [q, setQ] = useState("");
  const { value, edit, commit, dirty, saving } = useStructEditor<Record<string, string[]>>("module_access", server);
  const groups = useMemo(moduleGroups, []);
  const current = slug || roles[0]?.slug || "";
  if (!value) return null;
  const hidden = new Set(value[current] ?? []);
  const setHidden = (h: Set<string>) => edit({ ...value, [current]: [...h].sort() });
  const toggle = (hrefs: string[], on: boolean) => { const h = new Set(hidden); hrefs.forEach((x) => (on ? h.delete(x) : h.add(x))); setHidden(h); };
  const match = (s: string) => s.toLowerCase().includes(q.toLowerCase());
  const granted = groups.map((g) => ({ ...g, items: g.items.filter((i) => !hidden.has(i.href)) })).filter((g) => g.items.length);
  return (
    <Panel title="Module Permissions Manager">
      <div className="flex flex-wrap gap-3 mb-4">
        <select className="input max-w-xs" aria-label="Role" value={current} onChange={(e) => setSlug(e.target.value)}>
          {roles.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
        </select>
        <input className="input max-w-xs" placeholder="Search modules" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <p className="text-xs text-slate-500 mb-3">Untick a page to hide it (and block opening it) for this role. The Super User always sees everything.</p>
      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          {groups.map((g) => {
            const items = g.items.filter((i) => match(i.label) || match(g.label));
            if (!items.length) return null;
            const all = items.every((i) => !hidden.has(i.href));
            return (
              <div key={g.key} className="border border-slate-200 rounded-lg">
                <label className="flex items-center gap-2 px-3 py-2 bg-slate-50 font-bold text-sm">
                  <Check on={all} label={g.label} onChange={(v) => toggle(items.map((i) => i.href), v)} />{g.label}
                </label>
                <div className="grid sm:grid-cols-2 gap-x-4 px-3 py-2">
                  {items.map((i) => (
                    <label key={i.href} className="flex items-center gap-2 text-sm py-1">
                      <Check on={!hidden.has(i.href)} label={`${g.label} ${i.label}`} onChange={(v) => toggle([i.href], v)} />{i.label}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
          <SaveBar dirty={dirty} saving={saving} onSave={commit} label="Update" />
        </div>
        <div className="border border-slate-200 rounded-lg p-3 h-fit">
          <h3 className="font-bold text-sm mb-2">Module Granted Access</h3>
          {granted.map((g) => (
            <div key={g.key} className="mb-2"><div className="text-sm font-semibold">{g.label}</div>
              <ul className="ml-4 list-disc text-xs text-slate-600">{g.items.map((i) => <li key={i.href}>{i.label}</li>)}</ul></div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
