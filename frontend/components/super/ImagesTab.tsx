"use client";

import { useRef, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/utils";
import type { SuperField } from "@/lib/api";

const MIN: Record<string, string> = { login_image: "1389x920", main_logo: "113x112", general_logo: "200x40" };

function ImageBox({ f, value, onChange }: { f: SuperField; value: string; onChange: (v: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const pick = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api.post(`/super-settings/images/${f.key}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      onChange(r.data.url);
    } catch (e: any) {
      toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not upload the image.");
    } finally { setBusy(false); if (input.current) input.current.value = ""; }
  };
  return (
    <div className="py-4 border-b border-slate-100 last:border-0">
      <label className="block text-xs font-bold uppercase tracking-wide text-slate-600 mb-2">{f.label}:</label>
      <div className="w-full max-w-sm h-48 border border-slate-200 rounded-lg bg-white flex items-center justify-center overflow-hidden">
        {value ? <img src={resolveMediaUrl(value)} alt={f.label} className="max-h-full max-w-full object-contain" /> : <span className="text-sm text-slate-400">No image yet</span>}
      </div>
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => pick(e.target.files?.[0])} aria-label={`${f.label} file`} />
      <button type="button" onClick={() => input.current?.click()} disabled={busy} className="btn-secondary mt-2 gap-2">
        {busy && <Loader2 size={14} className="animate-spin" />} Select image
      </button>
      {value && <button type="button" onClick={() => onChange("")} className="ml-2 text-xs text-red-600 font-semibold">Remove</button>}
      <p className="text-xs text-slate-500 mt-2"><span className="bg-amber-400 text-white font-bold px-1.5 py-0.5 rounded mr-1">NOTE!</span>
        <em>Image dimensions should not be less than {MIN[f.key]} pixels(px).</em></p>
    </div>
  );
}

export function ImagesTab({ fields, values, onChange, onSave, dirty, saving }: {
  fields: SuperField[]; values: Record<string, any>; saved: Record<string, any>;
  onChange: (k: string, v: string) => void; onSave: () => void; dirty: boolean; saving: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6">
        {fields.map((f) => <ImageBox key={f.key} f={f} value={values[f.key] ?? ""} onChange={(v) => onChange(f.key, v)} />)}
      </div>
      <button onClick={onSave} disabled={!dirty || saving} className="btn-primary gap-2">
        {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Change
      </button>
    </div>
  );
}
