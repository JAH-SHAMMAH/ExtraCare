"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { biometricApi, platformApi } from "@/lib/api";
import type {
  BiometricDevice, BiometricEnrollment, UnmappedPunch, IngestSummary,
  AcademicSession, AcademicWeek, SchoolHouse, GradingBand, CustomFieldDef, Poll,
  MailboxMessage, MobileDevice, AppConfigItem, Paginated,
} from "@/types";

function inv(qc: ReturnType<typeof useQueryClient>, keys: string[]) {
  keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}
function m<T>(fn: (v: any) => Promise<T>, keys: string[], ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { inv(qc, keys); if (ok) toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

// ── Biometric ───────────────────────────────────────────────────────────────────
export function useDevices() { return useQuery<BiometricDevice[]>({ queryKey: ["bio-devices"], queryFn: () => biometricApi.devices.list() }); }
export function useEnrollments() { return useQuery<BiometricEnrollment[]>({ queryKey: ["bio-enrollments"], queryFn: () => biometricApi.enrollments.list() }); }
export function useQuarantine() { return useQuery<UnmappedPunch[]>({ queryKey: ["bio-quarantine"], queryFn: () => biometricApi.quarantine.list() }); }
export const useCreateDevice = m((d) => biometricApi.devices.create(d), ["bio-devices"], "Device registered.");
export const useDeleteDevice = m((id: string) => biometricApi.devices.remove(id), ["bio-devices"], "Device removed.");
export const useCreateEnrollment = m((d) => biometricApi.enrollments.create(d), ["bio-enrollments", "bio-quarantine"], "Mapped.");
export const useDeleteEnrollment = m((id: string) => biometricApi.enrollments.remove(id), ["bio-enrollments"], "Removed.");
export const useResolvePunch = m((v: { id: string; data: object }) => biometricApi.quarantine.resolve(v.id, v.data), ["bio-quarantine", "bio-enrollments"], "Resolved.");
export const useDiscardPunch = m((id: string) => biometricApi.quarantine.discard(id), ["bio-quarantine"], "Discarded.");

// ── School setup ──────────────────────────────────────────────────────────────
export function useSessions() { return useQuery<AcademicSession[]>({ queryKey: ["sessions"], queryFn: () => platformApi.sessions.list() }); }
export function useHouses() { return useQuery<SchoolHouse[]>({ queryKey: ["houses"], queryFn: () => platformApi.houses.list() }); }
export function useBands() { return useQuery<GradingBand[]>({ queryKey: ["bands"], queryFn: () => platformApi.bands.list() }); }
export const useCreateSession = m((d) => platformApi.sessions.create(d), ["sessions"], "Session saved.");
export const useDeleteSession = m((id: string) => platformApi.sessions.remove(id), ["sessions"], "Removed.");
export const useCreateHouse = m((d) => platformApi.houses.create(d), ["houses"], "House added.");
export const useDeleteHouse = m((id: string) => platformApi.houses.remove(id), ["houses"], "Removed.");
export const useCreateBand = m((d) => platformApi.bands.create(d), ["bands"], "Band added.");
export const useDeleteBand = m((id: string) => platformApi.bands.remove(id), ["bands"], "Removed.");

// ── Academic weeks (calendar backbone) ──────────────────────────────────────────
export function useWeeks(params?: { academic_year?: string; term?: string }) {
  return useQuery<AcademicWeek[]>({ queryKey: ["weeks", params], queryFn: () => platformApi.weeks.list(params) });
}
export const useCreateWeek = m((d) => platformApi.weeks.create(d), ["weeks"], "Week added.");
export const useGenerateWeeks = m((d) => platformApi.weeks.generate(d), ["weeks"], "Weeks generated.");
export const useUpdateWeek = m((v: { id: string; data: object }) => platformApi.weeks.update(v.id, v.data), ["weeks"], "Week updated.");
export const useDeleteWeek = m((id: string) => platformApi.weeks.remove(id), ["weeks"], "Removed.");

// ── Custom fields ──────────────────────────────────────────────────────────────
export function useCustomFields(entityType?: string) { return useQuery<CustomFieldDef[]>({ queryKey: ["custom-fields", entityType], queryFn: () => platformApi.customFields.list(entityType) }); }
export const useCreateField = m((d) => platformApi.customFields.create(d), ["custom-fields"], "Field added.");
export const useDeleteField = m((id: string) => platformApi.customFields.remove(id), ["custom-fields"], "Removed.");

// ── Voting ──────────────────────────────────────────────────────────────────────
export function usePolls(params?: { status?: string }) { return useQuery<Paginated<Poll>>({ queryKey: ["polls", params], queryFn: () => platformApi.polls.list(params) }); }
export const useCreatePoll = m((d) => platformApi.polls.create(d), ["polls"], "Poll created.");
export const useClosePoll = m((id: string) => platformApi.polls.close(id), ["polls"], "Poll closed.");
export const useDeletePoll = m((id: string) => platformApi.polls.remove(id), ["polls"], "Removed.");
export const useVote = m((v: { id: string; data: object }) => platformApi.polls.vote(v.id, v.data), ["polls"], "Vote cast.");

// ── Mailbox ─────────────────────────────────────────────────────────────────────
export function useSentMessages() { return useQuery<MailboxMessage[]>({ queryKey: ["mailbox-sent"], queryFn: () => platformApi.mailbox.sent() }); }
export function useInbox() { return useQuery<any[]>({ queryKey: ["mailbox-inbox"], queryFn: () => platformApi.mailbox.inbox() }); }
export const useSendMessage = m((d) => platformApi.mailbox.send(d), ["mailbox-sent"], "Sent.");
export const useMarkRead = m((rowId: string) => platformApi.mailbox.markRead(rowId), ["mailbox-inbox"], "");

// ── Mobile ──────────────────────────────────────────────────────────────────────
export function useMobileDevices() { return useQuery<MobileDevice[]>({ queryKey: ["mobile-devices"], queryFn: () => platformApi.mobile.devices() }); }
export function useAppConfig() { return useQuery<AppConfigItem[]>({ queryKey: ["app-config"], queryFn: () => platformApi.mobile.config() }); }
export const useDeleteMobileDevice = m((id: string) => platformApi.mobile.remove(id), ["mobile-devices"], "Removed.");
export const useSetConfig = m((d) => platformApi.mobile.setConfig(d), ["app-config"], "Saved.");
