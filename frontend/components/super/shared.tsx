"use client";

import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { useSaveSuperStruct } from "@/hooks/useSuperSettings";

/** A local copy of one structured setting, with a Save that writes just that key. */
export function useStructEditor<T>(key: string, server: T | undefined) {
  const [value, setValue] = useState<T | undefined>(server);
  const [dirty, setDirty] = useState(false);
  const save = useSaveSuperStruct();
  useEffect(() => { if (server !== undefined && !dirty) setValue(server); }, [server, dirty]);
  const edit = (v: T) => { setValue(v); setDirty(true); };
  const commit = () => save.mutate({ key, value }, {
    onSuccess: () => { setDirty(false); toast.success("Saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Could not save."),
  });
  return { value, edit, commit, dirty, saving: save.isPending };
}

export function SaveBar({ dirty, saving, onSave, label = "Save Setting" }: { dirty: boolean; saving: boolean; onSave: () => void; label?: string }) {
  return (
    <button onClick={onSave} disabled={!dirty || saving} className="btn-primary gap-2 mt-4">
      {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} {label}
    </button>
  );
}

export function Panel({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {title && <div className="bg-emerald-700 text-white px-4 py-3 font-bold">{title}</div>}
      <div className="p-4 sm:p-6">{children}</div>
    </div>
  );
}

export function Check({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return <input type="checkbox" aria-label={label} checked={on} onChange={(e) => onChange(e.target.checked)} className="h-5 w-5 rounded border-slate-300 accent-emerald-600" />;
}
