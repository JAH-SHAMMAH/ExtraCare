"use client";

import { useState } from "react";
import type { RolePerm } from "@/lib/api";
import { useAvailableRoles } from "@/hooks/useUsers";
import { Panel, Check, SaveBar, useStructEditor } from "@/components/super/shared";

export const roleList = (d: any): { slug: string; name: string }[] => (d?.items ?? d ?? []).map((r: any) => ({ slug: r.slug, name: r.name }));

export function RolePermsTab({ server, items }: { server: Record<string, RolePerm> | undefined; items: { key: string; label: string; help: string }[] }) {
  const { data } = useAvailableRoles();
  const roles = roleList(data);
  const [slug, setSlug] = useState("");
  const { value, edit, commit, dirty, saving } = useStructEditor<Record<string, RolePerm>>("role_perms", server);
  const current = slug || roles[0]?.slug || "";
  if (!value) return null;
  const rp: RolePerm | undefined = value[current];
  const patch = (p: Partial<RolePerm>) => rp && edit({ ...value, [current]: { ...rp, ...p } });
  return (
    <Panel title="User Role Permissions">
      <label className="label">Role</label>
      <select className="input max-w-xs mb-4" value={current} onChange={(e) => setSlug(e.target.value)} aria-label="Role">
        {roles.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
      </select>
      {rp && (
        <>
          <table className="w-full text-sm">
            <tbody>
              {items.map((it) => (
                <tr key={it.key} className="border-t">
                  <td className="p-2"><div className="font-semibold">{it.label}</div><div className="text-xs text-slate-400">{it.help}</div></td>
                  <td className="p-2 w-16"><Check on={!!(rp as any)[it.key]} label={it.label} onChange={(v) => patch({ [it.key]: v } as any)} /></td>
                </tr>
              ))}
              <tr className="border-t">
                <td className="p-2"><div className="font-semibold">Can Create Group</div><div className="text-xs text-slate-400">Start group chats in the messenger.</div></td>
                <td className="p-2 w-16"><Check on={rp.can_create_group} label="Can Create Group" onChange={(v) => patch({ can_create_group: v })} /></td>
              </tr>
            </tbody>
          </table>
          <h3 className="font-bold text-sm mt-5 mb-1">Roles this role can message</h3>
          <p className="text-xs text-slate-400 mb-2">Leave all unticked to allow everyone.</p>
          <div className="flex flex-wrap gap-4">
            {roles.map((r) => (
              <label key={r.slug} className="flex items-center gap-2 text-sm">
                <Check on={rp.message_roles.includes(r.slug)} label={`Message ${r.name}`}
                  onChange={(v) => patch({ message_roles: v ? [...rp.message_roles, r.slug] : rp.message_roles.filter((s) => s !== r.slug) })} />
                {r.name}
              </label>
            ))}
          </div>
          <SaveBar dirty={dirty} saving={saving} onSave={commit} />
        </>
      )}
    </Panel>
  );
}
