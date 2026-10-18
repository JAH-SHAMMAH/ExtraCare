"use client";

import { useState } from "react";
import { Panel, Check, SaveBar, useStructEditor } from "@/components/super/shared";
import { cn } from "@/lib/utils";

const OTHER = ["SMS", "Birthday", "Work Anniversary", "WhatsApp"];

export function NotificationsTab({ server, events }: {
  server: Record<string, { email: boolean; push: boolean }> | undefined; events: { key: string; label: string }[];
}) {
  const { value, edit, commit, dirty, saving } = useStructEditor<Record<string, { email: boolean; push: boolean }>>("notification_prefs", server);
  const [tab, setTab] = useState("Email/Push");
  if (!value) return null;
  const set = (k: string, ch: "email" | "push", v: boolean) => edit({ ...value, [k]: { ...(value[k] ?? { email: false, push: false }), [ch]: v } });
  return (
    <Panel title="Notification Settings">
      <div className="flex flex-wrap gap-4 border-b mb-4">
        {["Email/Push", ...OTHER].map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn("py-2 text-sm font-semibold border-b-2 -mb-px", tab === t ? "border-emerald-500 text-emerald-600" : "border-transparent text-slate-600")}>{t}</button>
        ))}
      </div>
      {tab === "Email/Push" ? (
        <>
          <p className="text-xs text-slate-500 mb-2">Push off means that alert is no longer sent to anyone&apos;s in-app inbox.</p>
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-50 text-left"><th className="p-2 w-14">S/N</th><th className="p-2">Event</th><th className="p-2 w-20">Email</th><th className="p-2 w-20">Push</th></tr></thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={e.key} className="border-t">
                  <td className="p-2">{i + 1}</td><td className="p-2">{e.label}</td>
                  <td className="p-2"><Check on={!!value[e.key]?.email} label={`${e.label} email`} onChange={(v) => set(e.key, "email", v)} /></td>
                  <td className="p-2"><Check on={!!value[e.key]?.push} label={`${e.label} push`} onChange={(v) => set(e.key, "push", v)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <SaveBar dirty={dirty} saving={saving} onSave={commit} />
        </>
      ) : (
        <p className="text-sm text-slate-500 py-6">{tab} messages need a {tab === "WhatsApp" ? "WhatsApp" : "SMS"} gateway, which isn&apos;t connected to this school yet. Once one is connected the events will be listed here.</p>
      )}
    </Panel>
  );
}
