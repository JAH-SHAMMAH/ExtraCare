"use client";

import { useState } from "react";
import {
  usePaymentGateways, useCreatePaymentGateway, useUpdatePaymentGateway, useDeletePaymentGateway,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { KeyRound, Plus, X, Loader2, Trash2, ShieldCheck, CheckCircle2, CircleDashed, Lock, AlertTriangle } from "lucide-react";
import type { PaymentGateway, GatewayProvider } from "@/types";

const PROVIDERS: { value: GatewayProvider; label: string }[] = [
  { value: "paystack", label: "Paystack" },
  { value: "remita", label: "Remita" },
  { value: "flutterwave", label: "Flutterwave" },
];
const providerLabel = (p: string) => PROVIDERS.find((x) => x.value === p)?.label ?? p;
// Providers whose credentials can be STORED but are not yet wired for live payments.
// All three (Paystack, Remita, Flutterwave) are now consumed — this stays as the hook
// for any FUTURE provider added to the UI ahead of its adapter.
const INACTIVE_PROVIDERS = new Set<GatewayProvider>([]);

type FormState = {
  provider: GatewayProvider;
  label: string;
  mode: "test" | "live";
  public_key: string;
  secret_key: string;
  webhook_secret: string;
  merchant_id: string;
  service_type_id: string;
  is_active: boolean;
};
const emptyForm = (provider: GatewayProvider): FormState => ({
  provider, label: "", mode: "test", public_key: "", secret_key: "", webhook_secret: "",
  merchant_id: "", service_type_id: "", is_active: true,
});

export default function PaymentGatewaysPage() {
  const canWrite = useHasPermission("payment_gateways:write");
  const { data: gateways, isLoading, isError, refetch } = usePaymentGateways();
  const create = useCreatePaymentGateway();
  const update = useUpdatePaymentGateway();
  const del = useDeletePaymentGateway();

  const [editing, setEditing] = useState<PaymentGateway | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const configured = new Set((gateways ?? []).map((g) => g.provider));
  const firstFree = PROVIDERS.find((p) => !configured.has(p.value))?.value ?? "paystack";

  const openNew = () => { setEditing(null); setForm(emptyForm(firstFree)); };
  const openEdit = (g: PaymentGateway) => {
    setEditing(g);
    setForm({ provider: g.provider, label: g.label ?? "", mode: g.mode, public_key: g.public_key ?? "",
              secret_key: "", webhook_secret: "", merchant_id: g.merchant_id ?? "", service_type_id: g.service_type_id ?? "",
              is_active: g.is_active });
  };
  const close = () => { setForm(null); setEditing(null); };

  const submit = () => {
    if (!form) return;
    const isRemita = form.provider === "remita";
    if (editing) {
      // Only send secret fields if the admin actually typed a new value.
      const data: Record<string, unknown> = {
        label: form.label || null, mode: form.mode, public_key: form.public_key || null, is_active: form.is_active,
      };
      if (form.secret_key) data.secret_key = form.secret_key;
      if (form.webhook_secret) data.webhook_secret = form.webhook_secret;
      if (isRemita) { data.merchant_id = form.merchant_id || null; data.service_type_id = form.service_type_id || null; }
      update.mutate({ id: editing.id, data }, { onSuccess: close });
    } else {
      create.mutate({
        provider: form.provider, label: form.label || null, mode: form.mode,
        public_key: form.public_key || null, secret_key: form.secret_key || null,
        webhook_secret: form.webhook_secret || null, is_active: form.is_active,
        ...(isRemita ? { merchant_id: form.merchant_id || null, service_type_id: form.service_type_id || null } : {}),
      }, { onSuccess: close });
    }
  };

  const saving = create.isPending || update.isPending;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-2 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Payment Gateways</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Payment Gateways</h1>
          <p className="text-slate-500 text-sm mt-0.5">Store this school&apos;s own gateway API credentials for collecting fees online.</p>
        </div>
        {canWrite && <button onClick={openNew} className="btn-primary gap-2"><Plus size={15} /> Add Gateway</button>}
      </div>

      <div className="flex items-start gap-2 rounded-lg bg-slate-50 border border-slate-200 px-4 py-3 mb-6 text-[12px] text-slate-500">
        <Lock size={15} className="shrink-0 mt-0.5 text-slate-400" />
        <p>Secret keys are <b>encrypted at rest</b> and never shown again after saving. You can rotate a secret any time by entering a new value; leaving it blank keeps the current one.</p>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-12 text-center text-slate-400">
          <p className="text-sm font-semibold">Couldn&apos;t load gateways</p>
          <button onClick={() => refetch()} className="btn-secondary text-xs mt-2">Retry</button>
        </div>
      ) : (gateways ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <KeyRound size={36} className="mx-auto mb-3 opacity-30" />
          <p className="font-semibold text-sm">No gateways configured</p>
          {canWrite && <p className="text-xs mt-1">Add Paystack, Remita or Flutterwave credentials with <b>Add Gateway</b>.</p>}
        </div>
      ) : (
        <div className="space-y-3">
          {(gateways ?? []).map((g) => (
            <div key={g.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-900">{providerLabel(g.provider)}</span>
                    <span className={cn("badge capitalize", g.mode === "live" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200")}>{g.mode}</span>
                    {!g.is_active && <span className="badge bg-slate-100 text-slate-500 border-slate-200">inactive</span>}
                    {INACTIVE_PROVIDERS.has(g.provider) && <span className="badge bg-orange-50 text-orange-700 border-orange-200">not yet live</span>}
                  </div>
                  {g.label && <p className="text-[12px] text-slate-500 mt-0.5">{g.label}</p>}
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2 text-[12px]">
                    {g.provider === "remita" ? (
                      <>
                        <SecretState label="Merchant ID" set={!!g.merchant_id} value={g.merchant_id} />
                        <SecretState label="Service Type" set={!!g.service_type_id} value={g.service_type_id} />
                        <SecretState label="API key" set={g.secret_key_set} />
                      </>
                    ) : (
                      <>
                        <SecretState label="Public key" set={!!g.public_key} value={g.public_key} />
                        <SecretState label="Secret key" set={g.secret_key_set} />
                        <SecretState label="Webhook secret" set={g.webhook_secret_set} />
                      </>
                    )}
                  </div>
                </div>
                {canWrite && (
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => openEdit(g)} className="btn-secondary text-xs">Edit</button>
                    <button onClick={() => { if (confirm(`Remove the ${providerLabel(g.provider)} gateway?`)) del.mutate(g.id); }} className="text-slate-400 hover:text-red-600"><Trash2 size={15} /></button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add / edit modal */}
      {form && canWrite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={close}>
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-800">{editing ? `Edit ${providerLabel(editing.provider)}` : "Add gateway"}</h2>
              <button onClick={close} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <div className="space-y-3">
              {INACTIVE_PROVIDERS.has(form.provider) && (
                <div className="flex items-start gap-2 rounded-lg bg-orange-50 border border-orange-200 px-3 py-2.5 text-[12px] text-orange-800">
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <p><b>{providerLabel(form.provider)} isn&apos;t live yet.</b> You can store its credentials here, but fee payments won&apos;t use it until support ships — they&apos;ll use a configured live gateway (e.g. Paystack/Remita) or return an error. Safe to pre-stage.</p>
                </div>
              )}
              {!editing && (
                <div>
                  <label className="label">Provider *</label>
                  <select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value as GatewayProvider })} className="input">
                    {PROVIDERS.map((p) => <option key={p.value} value={p.value} disabled={configured.has(p.value)}>{p.label}{configured.has(p.value) ? " (configured)" : INACTIVE_PROVIDERS.has(p.value) ? " — not yet live" : ""}</option>)}
                  </select>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Label</label><input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="input" placeholder="optional" /></div>
                <div>
                  <label className="label">Mode</label>
                  <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value as "test" | "live" })} className="input">
                    <option value="test">Test</option>
                    <option value="live">Live</option>
                  </select>
                </div>
              </div>
              {form.provider === "remita" ? (
                <>
                  {/* Remita uses a 3-part credential: merchant id + service-type id (non-secret) + API key (secret). */}
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="label">Merchant ID</label><input value={form.merchant_id} onChange={(e) => setForm({ ...form, merchant_id: e.target.value })} className="input" placeholder="e.g. 2547916" /></div>
                    <div><label className="label">Service Type ID</label><input value={form.service_type_id} onChange={(e) => setForm({ ...form, service_type_id: e.target.value })} className="input" placeholder="e.g. 4430731" /></div>
                  </div>
                  <div>
                    <label className="label">API key {editing && <span className="text-[10px] text-slate-400 font-normal">(leave blank to keep current)</span>}</label>
                    <input type="password" autoComplete="new-password" value={form.secret_key} onChange={(e) => setForm({ ...form, secret_key: e.target.value })} className="input" placeholder={editing && editing.secret_key_set ? "•••••••• (set)" : "Remita API key"} />
                  </div>
                </>
              ) : form.provider === "flutterwave" ? (
                <>
                  {/* Flutterwave: API secret key (FLWSECK_...) + the verif-hash Secret Hash for webhooks. */}
                  <div>
                    <label className="label">Secret key (API key) {editing && <span className="text-[10px] text-slate-400 font-normal">(leave blank to keep current)</span>}</label>
                    <input type="password" autoComplete="new-password" value={form.secret_key} onChange={(e) => setForm({ ...form, secret_key: e.target.value })} className="input" placeholder={editing && editing.secret_key_set ? "•••••••• (set)" : "FLWSECK_TEST-… / FLWSECK-…"} />
                  </div>
                  <div>
                    <label className="label">Secret hash (webhooks) {editing && <span className="text-[10px] text-slate-400 font-normal">(leave blank to keep current)</span>}</label>
                    <input type="password" autoComplete="new-password" value={form.webhook_secret} onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })} className="input" placeholder={editing && editing.webhook_secret_set ? "•••••••• (set)" : "the verif-hash you set in the FLW dashboard"} />
                  </div>
                </>
              ) : (
                <>
                  <div><label className="label">Public key</label><input value={form.public_key} onChange={(e) => setForm({ ...form, public_key: e.target.value })} className="input" placeholder="pk_..." /></div>
                  <div>
                    <label className="label">Secret key {editing && <span className="text-[10px] text-slate-400 font-normal">(leave blank to keep current)</span>}</label>
                    <input type="password" autoComplete="new-password" value={form.secret_key} onChange={(e) => setForm({ ...form, secret_key: e.target.value })} className="input" placeholder={editing && editing.secret_key_set ? "•••••••• (set)" : "sk_..."} />
                  </div>
                  <div>
                    <label className="label">Webhook secret {editing && <span className="text-[10px] text-slate-400 font-normal">(leave blank to keep current)</span>}</label>
                    <input type="password" autoComplete="new-password" value={form.webhook_secret} onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })} className="input" placeholder={editing && editing.webhook_secret_set ? "•••••••• (set)" : "optional"} />
                  </div>
                </>
              )}
              <label className="flex items-center gap-2 text-sm text-slate-600 pt-1">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="rounded border-slate-300" />
                Active
              </label>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mt-4"><ShieldCheck size={13} /> Secrets are encrypted before they touch the database.</div>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={close} className="btn-secondary">Cancel</button>
              <button onClick={submit} disabled={saving} className="btn-primary gap-2">{saving && <Loader2 size={15} className="animate-spin" />}{editing ? "Save changes" : "Add gateway"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SecretState({ label, set, value }: { label: string; set: boolean; value?: string | null }) {
  return (
    <div className="flex items-center gap-1.5">
      {set ? <CheckCircle2 size={13} className="text-emerald-500 shrink-0" /> : <CircleDashed size={13} className="text-slate-300 shrink-0" />}
      <span className="text-slate-400">{label}:</span>
      <span className={cn("truncate font-medium", set ? "text-slate-600" : "text-slate-400")}>
        {value ? value : set ? "set" : "not set"}
      </span>
    </div>
  );
}
