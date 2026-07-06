"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Send, Users as UsersIcon, GraduationCap, Heart, School, UserCheck,
  MessageSquare, Check, X, Loader2, AlertTriangle, Clock, Inbox,
  Eye, ChevronRight, CheckCircle2, Phone, RefreshCw,
} from "lucide-react";
import {
  useSendSms, useResendSms, useRecipientPreview, useSmsCampaigns, useSmsClasses,
  useSmsCampaign, type SmsTargetType, type SmsCampaignRow,
  type SmsMessageRow,
} from "@/hooks/useSms";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { TableSkeleton, Skeleton } from "@/components/loading/Skeleton";
import { cn, formatDate } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";

type Tab = "compose" | "logs";

const SMS_SEGMENT = 160;       // first segment
const SMS_SEGMENT_CONCAT = 153; // subsequent segments

export default function SmsPage() {
  const [tab, setTab] = useState<Tab>("compose");
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Communications</span><span>/</span>
            <span className="text-brand-600 font-semibold">Bulk SMS</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Bulk SMS</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Send a text message to parents, students, teachers, or a specific class.
          </p>
        </div>
      </div>

      {/* Honest status: no live SMS provider is wired yet. */}
      <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-6 text-[12px] text-amber-800">
        <AlertTriangle size={15} className="shrink-0 mt-0.5" />
        <p><b>Mock mode — messages are NOT delivered to real phones.</b> Campaigns are recorded and unit costs estimated so you can try the flow, but a live SMS provider hasn&apos;t been connected yet. Don&apos;t rely on this for real notifications until a provider is configured.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-1 inline-flex mb-5">
        {[
          { id: "compose" as Tab, label: "Compose", icon: Send },
          { id: "logs" as Tab, label: "Message Log", icon: Inbox },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "px-4 py-2 text-xs font-bold rounded-lg transition-colors flex items-center gap-2",
              tab === t.id ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            <t.icon size={13} />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "compose" ? (
        <ComposeTab onSent={() => setTab("logs")} />
      ) : (
        <LogsTab onOpen={(id) => setSelectedCampaignId(id)} />
      )}

      {selectedCampaignId && (
        <CampaignDrawer
          campaignId={selectedCampaignId}
          onClose={() => setSelectedCampaignId(null)}
        />
      )}
    </div>
  );
}

// ── Compose ──────────────────────────────────────────────────────────────────

interface TargetOption {
  type: SmsTargetType;
  label: string;
  icon: typeof UsersIcon;
  needsClass?: boolean;
  hint: string;
}

const TARGETS: TargetOption[] = [
  { type: "all_parents",   label: "All Parents",     icon: Heart,          hint: "Every parent/guardian with a phone on record" },
  { type: "all_students",  label: "All Students",    icon: GraduationCap,  hint: "Students across all classes" },
  { type: "all_teachers",  label: "All Teachers",    icon: UserCheck,      hint: "Teaching staff only" },
  { type: "class",         label: "Specific Class",  icon: School,         hint: "Students in one class", needsClass: true },
  { type: "class_parents", label: "Parents of a Class", icon: UsersIcon,   hint: "Only parents linked to that class", needsClass: true },
];

function ComposeTab({ onSent }: { onSent: () => void }) {
  const { org } = useAuthStore();
  const defaultSender = useMemo(() => deriveSenderId(org?.name ?? "ExtraCare"), [org?.name]);
  const [target, setTarget] = useState<TargetOption>(TARGETS[0]);
  const [classId, setClassId] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [senderId, setSenderId] = useState(defaultSender);
  const [showConfirm, setShowConfirm] = useState(false);

  // Keep sender in sync if the org name loads after first paint.
  useEffect(() => {
    setSenderId((s) => (s && s !== "EXTRACARE" ? s : defaultSender));
  }, [defaultSender]);

  const { data: classes } = useSmsClasses();
  const classList = classes?.items ?? [];

  // Preview query — only active once target selection is complete.
  const previewTarget = useMemo(() => {
    if (target.needsClass) {
      if (!classId) return null;
      return { target_type: target.type, target_value: classId };
    }
    return { target_type: target.type };
  }, [target, classId]);
  const { data: preview, isFetching: previewLoading } = useRecipientPreview(previewTarget);

  const send = useSendSms();

  const charCount = body.length;
  const unitCount = body.length === 0 ? 0
    : body.length <= SMS_SEGMENT ? 1
    : 1 + Math.ceil((body.length - SMS_SEGMENT) / SMS_SEGMENT_CONCAT);

  const canSend = Boolean(
    body.trim().length > 0
    && senderId.trim().length > 0
    && preview
    && preview.total > 0
    && !send.isPending,
  );

  const submit = async () => {
    if (!preview) return;
    await send.mutateAsync({
      body: body.trim(),
      target_type: target.type,
      target_value: target.needsClass ? classId : undefined,
      sender_id: senderId.trim(),
    });
    setBody("");
    setShowConfirm(false);
    onSent();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* LEFT: Form */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-6 space-y-5">
          {/* Target */}
          <div>
            <label className="label">Send to</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {TARGETS.map((opt) => {
                const Icon = opt.icon;
                const active = opt.type === target.type;
                return (
                  <button
                    key={opt.type}
                    type="button"
                    onClick={() => {
                      setTarget(opt);
                      if (!opt.needsClass) setClassId(null);
                    }}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-lg border text-left transition-colors",
                      active
                        ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500/20"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50",
                    )}
                  >
                    <div className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                      active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500",
                    )}>
                      <Icon size={14} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-slate-900 leading-tight">{opt.label}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{opt.hint}</p>
                    </div>
                    {active && <Check size={14} className="text-brand-600 shrink-0 mt-1" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Class picker — only when needed */}
          {target.needsClass && (
            <div>
              <label className="label">Which class?</label>
              <select
                value={classId ?? ""}
                onChange={(e) => setClassId(e.target.value || null)}
                className="input"
              >
                <option value="">Select a class…</option>
                {classList.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} · {c.student_count} student{c.student_count === 1 ? "" : "s"}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Sender ID */}
          <div>
            <label className="label">Sender ID</label>
            <div className="flex items-center gap-3">
              <input
                value={senderId}
                onChange={(e) => setSenderId(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 11))}
                maxLength={11}
                className="input font-mono text-sm"
              />
              <p className="text-[11px] text-slate-400 whitespace-nowrap">Max 11 characters</p>
            </div>
          </div>

          {/* Body */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="label mb-0">Message</label>
              <div className="flex items-center gap-3 text-[11px] font-semibold">
                <span className={cn("tabular-nums", charCount > 160 ? "text-amber-600" : "text-slate-500")}>
                  {charCount} chars
                </span>
                <span className="text-slate-400">·</span>
                <span className={cn("tabular-nums", unitCount > 1 ? "text-amber-600" : "text-slate-500")}>
                  {unitCount} SMS unit{unitCount === 1 ? "" : "s"}
                </span>
              </div>
            </div>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              placeholder="Type your message here…"
              className="input resize-y font-sans"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Over 160 characters splits into multiple SMS units (billed per unit).
            </p>
          </div>
        </div>

        <div className="sticky bottom-0 bg-slate-50 border-t border-slate-100 px-6 py-4 flex items-center justify-between">
          <div className="text-xs">
            {previewLoading ? (
              <span className="text-slate-400 flex items-center gap-1.5">
                <Loader2 size={12} className="animate-spin" /> Calculating recipients…
              </span>
            ) : preview ? (
              <span className="text-slate-600">
                Will send to <span className="font-black text-slate-900">{preview.total}</span>{" "}
                {preview.total === 1 ? "person" : "people"}
                {unitCount > 0 && (
                  <>
                    {" "}· <span className="font-bold">{preview.total * unitCount}</span> SMS units
                    {" "}·{" "}
                    <span className="font-bold text-slate-900">
                      ₦{(preview.total * unitCount * preview.unit_cost_ngn).toLocaleString("en-NG", { maximumFractionDigits: 2 })}
                    </span>
                  </>
                )}
              </span>
            ) : (
              <span className="text-slate-400">Select a target to see recipient count</span>
            )}
          </div>
          <button
            onClick={() => setShowConfirm(true)}
            disabled={!canSend}
            className="btn-primary gap-2"
          >
            <Send size={14} />
            Send SMS
          </button>
        </div>
      </div>

      {/* RIGHT: Recipient preview */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Recipients</p>
          <h3 className="text-sm font-bold text-slate-900 mt-0.5">
            {preview?.target_label || "—"}
          </h3>
        </div>
        <div className="divide-y divide-slate-50">
          {previewLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="px-5 py-3 flex items-center gap-3">
                <Skeleton className="h-8 w-8 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className="h-2 w-32" />
                </div>
              </div>
            ))
          ) : !preview ? (
            <div className="px-5 py-8 text-center text-xs text-slate-400">
              Pick a target to preview.
            </div>
          ) : preview.total === 0 ? (
            <div className="px-5 py-8 text-center">
              <AlertTriangle size={20} className="text-amber-500 mx-auto mb-2" />
              <p className="text-xs font-semibold text-slate-700">No recipients</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Nobody matches this target with a phone on file.</p>
            </div>
          ) : (
            <>
              {preview.sample.map((p) => (
                <div key={p.id} className="px-5 py-2.5 flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full bg-brand-50 text-brand-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                    {initials(p.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-slate-800 truncate">{p.name}</p>
                    <p className="text-[10px] text-slate-400 font-mono truncate">{p.phone ?? "—"}</p>
                  </div>
                </div>
              ))}
              {preview.total > preview.sample.length && (
                <div className="px-5 py-2.5 text-center text-[11px] text-slate-500">
                  + {preview.total - preview.sample.length} more
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Confirm modal */}
      {showConfirm && preview && (
        <ConfirmSendModal
          onCancel={() => setShowConfirm(false)}
          onConfirm={submit}
          recipientCount={preview.total}
          unitCount={unitCount}
          unitCostNgn={preview.unit_cost_ngn}
          body={body}
          targetLabel={preview.target_label}
          senderId={senderId}
          loading={send.isPending}
        />
      )}
    </div>
  );
}

function ConfirmSendModal({
  onCancel, onConfirm, recipientCount, unitCount, unitCostNgn, body, targetLabel, senderId, loading,
}: {
  onCancel: () => void;
  onConfirm: () => void;
  recipientCount: number;
  unitCount: number;
  unitCostNgn: number;
  body: string;
  targetLabel: string;
  senderId: string;
  loading: boolean;
}) {
  const totalCost = recipientCount * unitCount * unitCostNgn;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={loading ? undefined : onCancel} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-fade-in">
        <div className="p-6">
          <div className="flex items-start gap-4 mb-4">
            <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
              <Send size={18} />
            </div>
            <div>
              <h3 className="text-base font-black text-slate-900">Send this SMS?</h3>
              <p className="text-xs text-slate-500 mt-0.5">This can&apos;t be undone.</p>
            </div>
          </div>

          <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 space-y-2.5 text-sm">
            <Row label="Recipients" value={`${recipientCount} · ${targetLabel}`} />
            <Row label="SMS units" value={`${recipientCount * unitCount} (${unitCount} per recipient)`} />
            <Row
              label="Estimated cost"
              value={`₦${totalCost.toLocaleString("en-NG", { maximumFractionDigits: 2 })}`}
            />
            <Row label="Sender" value={senderId} mono />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Message</p>
              <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{body}</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-50 border-t border-slate-100 px-6 py-4 flex items-center justify-end gap-2">
          <button onClick={onCancel} disabled={loading} className="btn-secondary">Cancel</button>
          <button onClick={onConfirm} disabled={loading} className="btn-primary gap-2">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Send now
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
      <p className={cn("text-sm font-semibold text-slate-800 truncate", mono && "font-mono")}>{value}</p>
    </div>
  );
}

// ── Logs tab ─────────────────────────────────────────────────────────────────

function LogsTab({ onOpen }: { onOpen: (id: string) => void }) {
  const { data, isLoading } = useSmsCampaigns({ page_size: 50 });
  const showSkeleton = useDelayedFlag(isLoading);
  const resend = useResendSms();
  const campaigns = data?.items ?? [];

  if (showSkeleton) return <TableSkeleton rows={6} cols={5} />;
  if (campaigns.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
        <MessageSquare size={28} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm font-semibold text-slate-700">No SMS yet</p>
        <p className="text-xs text-slate-500 mt-1">Go to Compose to send your first message.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <table className="w-full text-left">
        <thead>
          <tr className="bg-slate-50/80 border-b border-slate-100">
            {["Message", "Audience", "Sent", "Delivered", "Cost", ""].map((h) => (
              <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {campaigns.map((c) => (
            <CampaignRow
              key={c.id}
              campaign={c}
              onOpen={() => onOpen(c.id)}
              onResend={() => {
                if (confirm(`Resend "${c.subject ?? "this message"}" to the same audience?`)) {
                  resend.mutate(c.id);
                }
              }}
              resending={resend.isPending && resend.variables === c.id}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CampaignRow({
  campaign, onOpen, onResend, resending,
}: { campaign: SmsCampaignRow; onOpen: () => void; onResend: () => void; resending: boolean }) {
  const hasFailures = campaign.failed_count > 0;
  const deliveryPct = campaign.total_recipients > 0
    ? Math.round((campaign.delivered_count / campaign.total_recipients) * 100)
    : 0;

  return (
    <tr className="group hover:bg-slate-50/60 transition-colors">
      <td onClick={onOpen} className="px-5 py-3.5 max-w-md cursor-pointer">
        {campaign.subject && (
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-0.5">{campaign.subject}</p>
        )}
        <p className="text-sm text-slate-800 line-clamp-2 leading-snug">{campaign.body}</p>
      </td>
      <td onClick={onOpen} className="px-5 py-3.5 cursor-pointer">
        <p className="text-sm font-semibold text-slate-800">{campaign.target_label}</p>
        <p className="text-xs text-slate-500">{campaign.total_recipients} recipient{campaign.total_recipients === 1 ? "" : "s"}</p>
      </td>
      <td onClick={onOpen} className="px-5 py-3.5 cursor-pointer">
        <p className="text-xs text-slate-500 tabular-nums">{formatDate(campaign.created_at)}</p>
        <p className="text-[10px] text-slate-400">by {campaign.created_by_name ?? "—"}</p>
      </td>
      <td onClick={onOpen} className="px-5 py-3.5 cursor-pointer">
        <div className="flex items-center gap-2">
          <div className={cn(
            "badge text-[10px]",
            hasFailures ? "bg-amber-50 text-amber-700 border-amber-200" :
              "bg-emerald-50 text-emerald-700 border-emerald-200",
          )}>
            {hasFailures ? <AlertTriangle size={10} className="mr-1" /> : <CheckCircle2 size={10} className="mr-1" />}
            {campaign.delivered_count}/{campaign.total_recipients}
          </div>
          <span className="text-[10px] text-slate-500 tabular-nums">{deliveryPct}%</span>
        </div>
      </td>
      <td onClick={onOpen} className="px-5 py-3.5 cursor-pointer">
        <p className="text-sm font-bold text-slate-900 tabular-nums">
          ₦{campaign.cost_ngn.toLocaleString("en-NG", { maximumFractionDigits: 2 })}
        </p>
        <p className="text-[10px] text-slate-400">{campaign.sms_units} unit{campaign.sms_units === 1 ? "" : "s"} × {campaign.total_recipients}</p>
      </td>
      <td className="px-5 py-3.5 text-right">
        <div className="flex items-center gap-1 justify-end">
          <button
            onClick={(e) => { e.stopPropagation(); onResend(); }}
            disabled={resending}
            className="p-1.5 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-100"
            title="Resend to current recipients"
          >
            {resending ? <Loader2 size={14} className="animate-spin text-brand-600" /> : <RefreshCw size={14} />}
          </button>
          <button onClick={onOpen} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100">
            <ChevronRight size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── Campaign detail drawer ───────────────────────────────────────────────────

function CampaignDrawer({ campaignId, onClose }: { campaignId: string; onClose: () => void }) {
  const { data, isLoading } = useSmsCampaign(campaignId);
  const showSkeleton = useDelayedFlag(isLoading);

  const campaign = data?.campaign;
  const messages = data?.messages ?? [];

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-xl bg-white shadow-2xl overflow-y-auto animate-slide-in flex flex-col">
        <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Campaign detail
            </p>
            <h2 className="text-lg font-black text-slate-900 truncate">
              {campaign?.subject || "Untitled campaign"}
            </h2>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
            <X size={18} />
          </button>
        </div>

        {showSkeleton || !campaign ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-36 w-full rounded-xl" />
          </div>
        ) : (
          <div className="p-6 space-y-5">
            {/* Stats strip */}
            <div className="grid grid-cols-3 gap-3">
              <StatTile
                label="Recipients"
                value={campaign.total_recipients}
                color="bg-slate-50 text-slate-700"
                icon={UsersIcon}
              />
              <StatTile
                label="Delivered"
                value={campaign.delivered_count}
                color="bg-emerald-50 text-emerald-700"
                icon={CheckCircle2}
              />
              <StatTile
                label="Failed"
                value={campaign.failed_count}
                color={campaign.failed_count ? "bg-rose-50 text-rose-700" : "bg-slate-50 text-slate-500"}
                icon={AlertTriangle}
              />
            </div>

            {/* Message */}
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">
                From {campaign.sender_id}
              </p>
              <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{campaign.body}</p>
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <MetaRow label="Audience" value={campaign.target_label ?? "—"} />
              <MetaRow label="Sent by" value={campaign.created_by_name ?? "—"} />
              <MetaRow label="Sent at" value={formatDate(campaign.created_at)} />
              <MetaRow label="Provider" value={campaign.provider} mono />
              <MetaRow label="Status" value={campaign.status} mono />
              <MetaRow label="SMS units" value={`${campaign.sms_units} × ${campaign.total_recipients}`} />
            </dl>

            {/* Per-recipient list */}
            <div>
              <h3 className="text-sm font-bold text-slate-800 mb-2">Delivery details ({messages.length})</h3>
              <div className="rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50 max-h-96 overflow-y-auto">
                {messages.map((m) => <MessageRow key={m.id} msg={m} />)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatTile({
  label, value, color, icon: Icon,
}: { label: string; value: number; color: string; icon: typeof UsersIcon }) {
  return (
    <div className={cn("rounded-xl px-4 py-3", color)}>
      <Icon size={14} className="opacity-70 mb-1" />
      <p className="text-xl font-black tabular-nums">{value}</p>
      <p className="text-[10px] font-bold uppercase tracking-widest opacity-70">{label}</p>
    </div>
  );
}

function MetaRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</dt>
      <dd className={cn("text-sm text-slate-800 mt-0.5 truncate", mono && "font-mono")}>{value}</dd>
    </div>
  );
}

function MessageRow({ msg }: { msg: SmsMessageRow }) {
  const ok = msg.status === "delivered";
  const failed = msg.status === "failed";
  return (
    <div className="px-4 py-2.5 flex items-center gap-3 hover:bg-slate-50">
      <div className={cn(
        "w-7 h-7 rounded-full flex items-center justify-center shrink-0",
        ok ? "bg-emerald-50 text-emerald-700" : failed ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-500",
      )}>
        {ok ? <Check size={12} /> : failed ? <X size={12} /> : <Clock size={12} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-800 truncate">{msg.recipient_name ?? "—"}</p>
        <p className="text-[11px] text-slate-400 font-mono truncate">{msg.recipient_phone}</p>
      </div>
      <div className="text-right">
        <p className={cn(
          "text-[10px] font-bold uppercase tracking-widest",
          ok ? "text-emerald-600" : failed ? "text-rose-600" : "text-slate-400",
        )}>{msg.status}</p>
        {failed && msg.error_message && (
          <p className="text-[10px] text-rose-500 mt-0.5 max-w-[140px] truncate" title={msg.error_message}>
            {msg.error_message}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Utils ────────────────────────────────────────────────────────────────────

function initials(name: string | null): string {
  if (!name) return "?";
  return name.split(" ").map((p) => p[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
}

function deriveSenderId(orgName: string): string {
  const cleaned = orgName.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
  return (cleaned || "EXTRACARE").slice(0, 11);
}
