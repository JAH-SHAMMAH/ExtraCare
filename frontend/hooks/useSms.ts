"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { smsApi } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

export type SmsTargetType =
  | "all_students"
  | "all_parents"
  | "all_teachers"
  | "class"
  | "class_parents"
  | "custom";

export type SmsCampaignStatus = "queued" | "sending" | "completed" | "failed";
export type SmsMessageStatus = "pending" | "sent" | "delivered" | "failed";

export interface SmsCampaignRow {
  id: string;
  subject: string | null;
  body: string;
  sender_id: string;
  provider: string;
  target_type: SmsTargetType;
  target_value: unknown;
  target_label: string | null;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  status: SmsCampaignStatus;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  completed_at: string | null;
  sms_units: number;
  cost_ngn: number;
  unit_cost_ngn: number;
}

export interface SmsMessageRow {
  id: string;
  recipient_user_id: string | null;
  recipient_name: string | null;
  recipient_phone: string;
  status: SmsMessageStatus;
  error_message: string | null;
  sent_at: string | null;
  delivered_at: string | null;
}

export interface SmsClassOption {
  id: string;
  name: string;
  level: string | null;
  student_count: number;
}

export interface RecipientPreview {
  target_type: SmsTargetType;
  target_label: string;
  total: number;
  sample: Array<{ id: string; name: string; phone: string | null }>;
  unit_cost_ngn: number;
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useSmsClasses() {
  return useQuery<{ items: SmsClassOption[] }>({
    queryKey: ["sms", "classes"],
    queryFn: () => smsApi.classes(),
    staleTime: 60_000,
  });
}

export function useRecipientPreview(target: { target_type: string; target_value?: string } | null) {
  return useQuery<RecipientPreview>({
    queryKey: ["sms", "preview", target],
    queryFn: () => smsApi.previewRecipients(target!),
    enabled: !!target?.target_type,
    // Previews are cheap; keep them fresh as the admin flips options.
    staleTime: 10_000,
  });
}

export function useSmsCampaigns(params?: { status?: string; page?: number; page_size?: number }) {
  return useQuery<{ items: SmsCampaignRow[]; total: number }>({
    queryKey: ["sms", "campaigns", params],
    queryFn: () => smsApi.list(params),
    staleTime: 15_000,
  });
}

export function useSmsCampaign(id: string | null) {
  return useQuery<{ campaign: SmsCampaignRow; messages: SmsMessageRow[] }>({
    queryKey: ["sms", "campaigns", id],
    queryFn: () => smsApi.get(id!),
    enabled: !!id,
    staleTime: 15_000,
  });
}

export function useResendSms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: string) => smsApi.resend(campaignId),
    onSuccess: (data: SmsCampaignRow) => {
      qc.invalidateQueries({ queryKey: ["sms"] });
      toast.success(`Resent — ${data.delivered_count}/${data.total_recipients} delivered`);
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to resend campaign.")),
  });
}

export function useSendSms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      body: string;
      target_type: string;
      target_value?: unknown;
      sender_id?: string;
      subject?: string;
    }) => smsApi.send(data),
    onSuccess: (data: SmsCampaignRow) => {
      qc.invalidateQueries({ queryKey: ["sms"] });
      const summary = `${data.delivered_count}/${data.total_recipients} delivered`;
      toast.success(`SMS sent — ${summary}`);
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to send SMS.")),
  });
}
