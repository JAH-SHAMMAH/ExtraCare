"use client";

import { useState } from "react";
import { useMobileDevices, useDeleteMobileDevice, useAppConfig, useSetConfig } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { MonitorCheck, Smartphone, Trash2, Plus, Loader2, AlertTriangle, Settings2 } from "lucide-react";

type Tab = "devices" | "config";

export default function MobileManagerPage() {
  const canWrite = useHasPermission("settings:write");
  const [tab, setTab] = useState<Tab>("devices");
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-5">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">Mobile Manager</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Mobile Manager</h1>
        <p className="text-slate-500 text-sm mt-0.5">Registered devices / push tokens and app-config toggles.</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["devices", "Devices"], ["config", "App Config"]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {tab === "devices" ? <Devices canWrite={canWrite} /> : <Config canWrite={canWrite} />}
    </div>
  );
}

function Devices({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useMobileDevices();
  const del = useDeleteMobileDevice();
  if (isLoading) return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>;
  if (isError) return <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load devices.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>;
  if ((data ?? []).length === 0) return <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Smartphone size={36} className="mb-3 opacity-40" /><p className="font-semibold">No devices registered</p><p className="text-xs mt-1">Devices self-register from the mobile app.</p></div>;
  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
      {data!.map((d) => (
        <div key={d.id} className="flex items-center gap-3 px-5 py-3.5">
          <Smartphone size={16} className="text-slate-300" />
          <div className="flex-1"><p className="text-sm font-medium text-slate-800">{d.label || d.platform || "Device"}</p><p className="text-xs font-mono text-slate-400 truncate max-w-[260px]">{d.push_token}</p></div>
          {d.platform && <span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{d.platform}</span>}
          <span className="text-xs text-slate-400">{d.last_seen_at ? formatDate(d.last_seen_at) : ""}</span>
          {canWrite && <button onClick={() => del.mutate(d.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
        </div>
      ))}
    </div>
  );
}

function Config({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useAppConfig();
  const setCfg = useSetConfig();
  const [f, setF] = useState({ key: "", value: "", description: "" });
  return (
    <>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div><label className="label">Key *</label><input value={f.key} onChange={(e) => setF({ ...f, key: e.target.value })} className="input" placeholder="min_app_version" /></div>
          <div><label className="label">Value</label><input value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} className="input" placeholder="2.4.0" /></div>
          <div><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" /></div>
          <button onClick={() => setCfg.mutate({ key: f.key.trim(), value: f.value || null, description: f.description || null }, { onSuccess: () => setF({ key: "", value: "", description: "" }) })} disabled={!f.key.trim() || setCfg.isPending} className="btn-primary justify-center">{setCfg.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}</button>
        </div>
      )}
      {isLoading ? <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
        : (data ?? []).length === 0 ? <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Settings2 size={36} className="mb-3 opacity-40" /><p className="font-semibold">No config keys</p></div>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {data!.map((c) => (
              <div key={c.id} className="flex items-center gap-3 px-5 py-3">
                <span className="text-sm font-mono font-semibold text-slate-700">{c.key}</span>
                <span className="text-sm text-slate-600">{c.value || "—"}</span>
                <span className="text-xs text-slate-400 ml-auto">{c.description || ""}</span>
              </div>
            ))}
          </div>
        )}
    </>
  );
}
