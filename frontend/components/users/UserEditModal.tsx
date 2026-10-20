"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { schoolApi, usersApi } from "@/lib/api";
import { useSections } from "@/hooks/usePlatform";
import { isTeachingRoleSlug } from "@/lib/teachingRoles";
import { FormField } from "@/components/ui/FormField";
import type { User } from "@/types";

interface Props {
  user: User | null;                 // null = closed
  availableRoles: Array<{ id: string; name: string; slug: string; color?: string }>;
  onClose: () => void;
  /** Open with the roles section in view (the "Change role" menu item). */
  focus?: "profile" | "roles";
}

const msg = (e: any, fallback: string) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join("; ") : fallback;
};

export function UserEditModal({ user, availableRoles, onClose, focus = "profile" }: Props) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ full_name: "", phone: "", department: "", job_title: "" });
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [sectionIds, setSectionIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const { data: sectionList } = useSections();
  const sections: Array<{ id: string; name: string }> = Array.isArray(sectionList) ? sectionList : [];

  const originalRoleIds = useMemo(() => (user?.roles ?? []).map((r) => r.id), [user]);
  const hadTeachingRole = useMemo(() => (user?.roles ?? []).some((r) => isTeachingRoleSlug(r.slug)), [user]);

  // Current sections — only teachers have any; a 404 for everyone else is expected.
  const current = useQuery({
    queryKey: ["user-edit-sections", user?.id],
    enabled: !!user && hadTeachingRole,
    retry: false,
    queryFn: () => schoolApi.teachers.get(user!.id).catch(() => null),
  });

  useEffect(() => {
    if (!user) return;
    setForm({ full_name: user.full_name || "", phone: user.phone || "", department: user.department || "", job_title: user.job_title || "" });
    setRoleIds(originalRoleIds);
    setError("");
  }, [user, originalRoleIds]);
  useEffect(() => { if (current.data?.section_ids) setSectionIds(current.data.section_ids); }, [current.data]);

  if (!user) return null;

  const needsSection = availableRoles.some((r) => roleIds.includes(r.id) && isTeachingRoleSlug(r.slug));
  const rolesChanged = roleIds.slice().sort().join() !== originalRoleIds.slice().sort().join();
  const toggle = (list: string[], set: (v: string[]) => void, id: string) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  const save = async () => {
    setError("");
    if (!form.full_name.trim()) { setError("Full name is required."); return; }
    if (roleIds.length === 0) { setError("Select at least one role."); return; }
    if (needsSection && sectionIds.length === 0) { setError("Choose at least one section for a teacher."); return; }
    setBusy(true);
    try {
      await usersApi.update(user.id, {
        full_name: form.full_name.trim(), phone: form.phone.trim() || null,
        department: form.department.trim() || null, job_title: form.job_title.trim() || null,
      });
      // Order matters: the server refuses a teaching role until a section is on file.
      if (needsSection) await usersApi.setSections(user.id, sectionIds);
      if (rolesChanged) await usersApi.assignRoles(user.id, roleIds);
      toast.success("User updated.");
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["staff"] });
      qc.invalidateQueries({ queryKey: ["teachers"] });
      onClose();
    } catch (e: any) {
      setError(msg(e, "Could not save changes."));
    } finally { setBusy(false); }
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={busy ? undefined : onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto pointer-events-auto" role="dialog" aria-label="Edit user">
          <div className="sticky top-0 bg-white border-b border-slate-200 px-5 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">{focus === "roles" ? "Change role" : "Edit user"}</h2>
              <p className="text-xs text-slate-500">{user.email}</p>
            </div>
            <button onClick={onClose} disabled={busy} className="p-2 hover:bg-slate-100 rounded-lg" aria-label="Close"><X size={18} className="text-slate-400" /></button>
          </div>

          <div className="p-5 space-y-4">
            <FormField label="Full name" required>
              <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} disabled={busy} />
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="Phone"><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} disabled={busy} /></FormField>
              <FormField label="Department"><input className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} disabled={busy} /></FormField>
            </div>
            <FormField label="Job title"><input className="input" value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} disabled={busy} /></FormField>

            <FormField label="Roles" required>
              <div className="space-y-1.5">
                {availableRoles.map((r) => (
                  <label key={r.id} className="flex items-center gap-3 p-2 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                    <input type="checkbox" className="w-4 h-4" checked={roleIds.includes(r.id)} onChange={() => toggle(roleIds, setRoleIds, r.id)} disabled={busy} />
                    <span className="text-sm font-medium text-slate-900">{r.name}</span>
                    <span className="text-xs text-slate-400">{r.slug}</span>
                  </label>
                ))}
              </div>
            </FormField>

            {needsSection && (
              <FormField label="Section" required>
                <div className="flex flex-wrap gap-2">
                  {sections.map((s) => (
                    <label key={s.id} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm font-medium ${sectionIds.includes(s.id) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`}>
                      <input type="checkbox" className="w-4 h-4" checked={sectionIds.includes(s.id)} onChange={() => toggle(sectionIds, setSectionIds, s.id)} disabled={busy} />
                      {s.name}
                    </label>
                  ))}
                </div>
              </FormField>
            )}

            {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2" role="alert">{error}</p>}
          </div>

          <div className="sticky bottom-0 bg-white border-t border-slate-200 px-5 py-3 flex gap-3">
            <button onClick={onClose} disabled={busy} className="btn-secondary flex-1">Cancel</button>
            <button onClick={save} disabled={busy} className="btn-primary flex-1 gap-2 justify-center">
              {busy && <Loader2 size={15} className="animate-spin" />}Save changes
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
