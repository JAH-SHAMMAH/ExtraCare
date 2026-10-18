"use client";

import { Panel, Check, SaveBar, useStructEditor } from "@/components/super/shared";

/** Educare-style "S/N · Name · Value (checkbox)" table. Used by the student and teacher dashboard settings. */
export function ChecklistTab({ title, structKey, items, server }: {
  title: string; structKey: string; items: { key: string; label: string }[]; server: Record<string, boolean> | undefined;
}) {
  const { value, edit, commit, dirty, saving } = useStructEditor<Record<string, boolean>>(structKey, server);
  if (!value) return null;
  return (
    <Panel title={title}>
      <table className="w-full text-sm border border-slate-200">
        <thead><tr className="bg-slate-50 text-left"><th className="p-2 w-14">S/N</th><th className="p-2">Name</th><th className="p-2 w-20">Value</th></tr></thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={it.key} className="border-t border-slate-200">
              <td className="p-2 align-top">{i + 1}</td><td className="p-2 align-top">{it.label}</td>
              <td className="p-2"><Check on={!!value[it.key]} label={it.label} onChange={(v) => edit({ ...value, [it.key]: v })} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <SaveBar dirty={dirty} saving={saving} onSave={commit} />
    </Panel>
  );
}
