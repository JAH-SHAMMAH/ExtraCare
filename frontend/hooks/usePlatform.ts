"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { biometricApi, platformApi } from "@/lib/api";
import type {
  BiometricDevice, BiometricEnrollment, UnmappedPunch, IngestSummary, DeviceToken,
  BiometricSummary, AttendanceHistoryRow, BiometricCommand,
  AcademicSession, AcademicWeek, SchoolHouse, GradingBand, CustomFieldDef, Poll,
  SchoolSection, GradingScale, ReportTemplate, AutoMapResult, SubjectAssessment,
  AssessmentDomain,
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
export const useCreateDevice = m((d) => biometricApi.devices.create(d), ["bio-devices", "bio-summary"], "Device registered.");
export const useDeleteDevice = m((id: string) => biometricApi.devices.remove(id), ["bio-devices", "bio-summary"], "Device removed.");
// Custom (not the `m` helper) because the caller needs the returned plaintext token.
export function useIssueDeviceToken() {
  const qc = useQueryClient();
  return useMutation<DeviceToken, any, string>({
    mutationFn: (id: string) => biometricApi.devices.issueToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bio-devices"] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to issue token."),
  });
}
export const useRevokeDeviceToken = m((id: string) => biometricApi.devices.revokeToken(id), ["bio-devices"], "Token revoked.");
export const useCreateEnrollment = m((d) => biometricApi.enrollments.create(d), ["bio-enrollments", "bio-quarantine", "bio-summary"], "Registered.");
export const useDeleteEnrollment = m((id: string) => biometricApi.enrollments.remove(id), ["bio-enrollments", "bio-summary"], "Removed.");
export const useResolvePunch = m((v: { id: string; data: object }) => biometricApi.quarantine.resolve(v.id, v.data), ["bio-quarantine", "bio-enrollments"], "Resolved.");
export const useDiscardPunch = m((id: string) => biometricApi.quarantine.discard(id), ["bio-quarantine"], "Discarded.");
export const useUpdateDevice = m((v: { id: string; data: object }) => biometricApi.devices.update(v.id, v.data), ["bio-devices"], "Device updated.");
export function useBiometricSummary() { return useQuery<BiometricSummary>({ queryKey: ["bio-summary"], queryFn: () => biometricApi.summary() }); }
export function useAttendanceHistory(deviceId?: string) { return useQuery<AttendanceHistoryRow[]>({ queryKey: ["bio-attendance", deviceId ?? "all"], queryFn: () => biometricApi.attendance(deviceId) }); }
export function useBiometricCommands(devicePk?: string) { return useQuery<BiometricCommand[]>({ queryKey: ["bio-commands", devicePk ?? "all"], queryFn: () => biometricApi.commands.list(devicePk) }); }
export const useGenerateCommand = m((v: { devicePk: string; data: object }) => biometricApi.commands.generate(v.devicePk, v.data), ["bio-commands"], "Command queued.");
export const useDeleteCommand = m((id: string) => biometricApi.commands.remove(id), ["bio-commands"], "Command removed.");

// ── School setup ──────────────────────────────────────────────────────────────
export function useSessions() { return useQuery<AcademicSession[]>({ queryKey: ["sessions"], queryFn: () => platformApi.sessions.list() }); }
// The org's current session/term, for term-consuming forms to default from.
export function useCurrentSession() {
  return useQuery<{ session: AcademicSession | null; term: string | null; name: string | null }>({
    queryKey: ["current-session"],
    queryFn: () => platformApi.sessions.current(),
    staleTime: 5 * 60 * 1000,
    // Resolver is school:read; non-staff consumers (e.g. a student on the CBT page)
    // get a 403 — fail quietly to a null default rather than retrying.
    retry: false,
  });
}
// Convenience: the current term ("" when none) for defaulting a term field.
export function useCurrentTerm(): string {
  const { data } = useCurrentSession();
  return data?.term ?? "";
}
// A term state seeded from the org's current term: applies it once when it loads,
// but never overrides a value the user has picked (touched wins). `fallback` is
// the value used until/unless a current term exists.
export function useTermState(fallback = ""): [string, (v: string) => void] {
  const current = useCurrentTerm();
  const [term, setTermRaw] = useState(fallback);
  const touched = useRef(false);
  useEffect(() => { if (!touched.current && current) setTermRaw(current); }, [current]);
  return [term, (v: string) => { touched.current = true; setTermRaw(v); }];
}
export function useHouses() { return useQuery<SchoolHouse[]>({ queryKey: ["houses"], queryFn: () => platformApi.houses.list() }); }
export function useBands() { return useQuery<GradingBand[]>({ queryKey: ["bands"], queryFn: () => platformApi.bands.list() }); }
export const useCreateSession = m((d) => platformApi.sessions.create(d), ["sessions", "current-session"], "Session saved.");
export const useUpdateSession = m((v: { id: string; data: object }) => platformApi.sessions.update(v.id, v.data), ["sessions", "current-session"], "Session updated.");
export const useDeleteSession = m((id: string) => platformApi.sessions.remove(id), ["sessions", "current-session"], "Removed.");
export const useCreateHouse = m((d) => platformApi.houses.create(d), ["houses"], "House added.");
export const useUpdateHouse = m((v: { id: string; data: object }) => platformApi.houses.update(v.id, v.data), ["houses"], "House updated.");
export const useDeleteHouse = m((id: string) => platformApi.houses.remove(id), ["houses"], "Removed.");
export const useCreateBand = m((d) => platformApi.bands.create(d), ["bands"], "Band added.");
export const useDeleteBand = m((id: string) => platformApi.bands.remove(id), ["bands"], "Removed.");

// ── School Reports R2 config: sections / grading scales / report templates ────────
export function useSections() { return useQuery<SchoolSection[]>({ queryKey: ["sections"], queryFn: () => platformApi.sections.list() }); }
export function useGradingScales() { return useQuery<GradingScale[]>({ queryKey: ["grading-scales"], queryFn: () => platformApi.gradingScales.list() }); }
export function useReportTemplates() { return useQuery<ReportTemplate[]>({ queryKey: ["report-templates"], queryFn: () => platformApi.reportTemplates.list() }); }
export const useCreateSection = m((d) => platformApi.sections.create(d), ["sections"], "Section added.");
export const useUpdateSection = m((v: { id: string; data: object }) => platformApi.sections.update(v.id, v.data), ["sections"], "Section updated.");
export const useDeleteSection = m((id: string) => platformApi.sections.remove(id), ["sections", "report-templates"], "Removed.");
export const useCreateScale = m((d) => platformApi.gradingScales.create(d), ["grading-scales"], "Scale added.");
export const useReplaceScaleBands = m((v: { id: string; bands: object[] }) => platformApi.gradingScales.replaceBands(v.id, v.bands), ["grading-scales"], "Bands saved.");
export const useDeleteScale = m((id: string) => platformApi.gradingScales.remove(id), ["grading-scales", "report-templates"], "Removed.");
export const useCreateTemplate = m((d) => platformApi.reportTemplates.create(d), ["report-templates"], "Template added.");
export const useUpdateTemplate = m((v: { id: string; data: object }) => platformApi.reportTemplates.update(v.id, v.data), ["report-templates"], "Template updated.");
export const useDeleteTemplate = m((id: string) => platformApi.reportTemplates.remove(id), ["report-templates"], "Removed.");
export const useBootstrapReportConfig = m(() => platformApi.reportTemplates.bootstrap(), ["sections", "grading-scales", "report-templates", "section-subjects"], "Standard report config created.");

// R2b — per-section subject Cambridge overlay.
export function useSectionSubjects(sectionId: string) {
  return useQuery<SubjectAssessment[]>({
    queryKey: ["section-subjects", sectionId],
    queryFn: () => platformApi.sections.subjects(sectionId),
    enabled: !!sectionId,
  });
}
export const useSetSectionSubject = m((v: { section_id: string; subject_id: string; data: object }) => platformApi.sections.setSubject(v.section_id, v.subject_id, v.data), ["section-subjects"], "Updated.");
export const useSetAllCambridge = m((v: { section_id: string; data: object }) => platformApi.sections.setAllCambridge(v.section_id, v.data), ["section-subjects"], "Applied to all subjects.");

// R3 — per-section assessment domains (EYFS areas/goals, skills, Cambridge strands).
export function useSectionDomains(sectionId: string) {
  return useQuery<AssessmentDomain[]>({
    queryKey: ["section-domains", sectionId],
    queryFn: () => platformApi.sections.domains(sectionId),
    enabled: !!sectionId,
  });
}
export const useSeedDomains = m((sectionId: string) => platformApi.sections.seedDomains(sectionId), ["section-domains"], "Standard domains created.");
export const useCreateDomain = m((v: { section_id: string; data: object }) => platformApi.sections.createDomain(v.section_id, v.data), ["section-domains"], "Domain added.");
export const useUpdateDomain = m((v: { id: string; data: object }) => platformApi.domains.update(v.id, v.data), ["section-domains"], "Domain updated.");
export const useDeleteDomain = m((id: string) => platformApi.domains.remove(id), ["section-domains"], "Domain removed.");

export function useAutoMapSections() {
  const qc = useQueryClient();
  return useMutation<AutoMapResult, any, void>({
    mutationFn: () => platformApi.sections.autoMap(),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success(`${res.linked} class(es) linked${res.unassigned.length ? `, ${res.unassigned.length} left unassigned` : ""}.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Auto-map failed."),
  });
}

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

// ── Secondary Report parity S-0: Terms & Sub-term + periods + deadlines ──────
export function useTerms() { return useQuery<any[]>({ queryKey: ["academic-terms"], queryFn: () => platformApi.terms.list() }); }
export function useSubTerms() { return useQuery<any[]>({ queryKey: ["academic-sub-terms"], queryFn: () => platformApi.subTerms.list() }); }
export const useBootstrapTerms = m(() => platformApi.terms.bootstrap(), ["academic-terms", "academic-sub-terms"], "Terms seeded.");
export const useCreateTerm = m((d) => platformApi.terms.create(d), ["academic-terms"], "Term added.");
export const useUpdateTerm = m((v: { id: string; data: object }) => platformApi.terms.update(v.id, v.data), ["academic-terms"], "Updated.");
export const useDeleteTerm = m((id: string) => platformApi.terms.remove(id), ["academic-terms"], "Removed.");
export const useCreateSubTerm = m((d) => platformApi.subTerms.create(d), ["academic-sub-terms"], "Sub-term added.");
export const useUpdateSubTerm = m((v: { id: string; data: object }) => platformApi.subTerms.update(v.id, v.data), ["academic-sub-terms"], "Updated.");
export const useDeleteSubTerm = m((id: string) => platformApi.subTerms.remove(id), ["academic-sub-terms"], "Removed.");

export function useTermPeriods(sessionId?: string) {
  return useQuery<any[]>({ queryKey: ["term-periods", sessionId ?? "all"], queryFn: () => platformApi.termPeriods.list(sessionId), enabled: !!sessionId });
}
export const useUpsertTermPeriod = m((d) => platformApi.termPeriods.upsert(d), ["term-periods"], "Saved.");
export const useDeleteTermPeriod = m((id: string) => platformApi.termPeriods.remove(id), ["term-periods"], "Removed.");

export function useReportDeadlines(sessionId?: string) {
  return useQuery<any[]>({ queryKey: ["report-deadlines", sessionId ?? "all"], queryFn: () => platformApi.reportDeadlines.list(sessionId), enabled: !!sessionId });
}
export const useCreateDeadline = m((d) => platformApi.reportDeadlines.create(d), ["report-deadlines"], "Deadline added.");
export const useUpdateDeadline = m((v: { id: string; data: object }) => platformApi.reportDeadlines.update(v.id, v.data), ["report-deadlines"], "Updated.");
export const useDeleteDeadline = m((id: string) => platformApi.reportDeadlines.remove(id), ["report-deadlines"], "Removed.");

// ── S-1a: Comment types + Result Default Comments ────────────────────────────
export function useCommentTypes() { return useQuery<any[]>({ queryKey: ["comment-types"], queryFn: () => platformApi.commentTypes.list() }); }
export const useCreateCommentType = m((d) => platformApi.commentTypes.create(d), ["comment-types"], "Comment type added.");
export const useUpdateCommentType = m((v: { id: string; data: object }) => platformApi.commentTypes.update(v.id, v.data), ["comment-types"], "Updated.");
export const useDeleteCommentType = m((id: string) => platformApi.commentTypes.remove(id), ["comment-types"], "Removed.");

export function useDefaultComments(params?: { teacher_type?: string; grading_scale_id?: string; year_group?: string }) {
  return useQuery<any[]>({ queryKey: ["default-comments", params], queryFn: () => platformApi.defaultComments.list(params) });
}
export const useCreateDefaultComment = m((d) => platformApi.defaultComments.create(d), ["default-comments"], "Comment added.");
export const useUpdateDefaultComment = m((v: { id: string; data: object }) => platformApi.defaultComments.update(v.id, v.data), ["default-comments"], "Updated.");
export const useDeleteDefaultComment = m((id: string) => platformApi.defaultComments.remove(id), ["default-comments"], "Removed.");

// ── S-1b: Grading scale update + report branding ─────────────────────────────
export const useUpdateScale = m((v: { id: string; data: object }) => platformApi.gradingScales.update(v.id, v.data), ["grading-scales"], "Updated.");
export function useReportBranding() { return useQuery<any>({ queryKey: ["report-branding"], queryFn: () => platformApi.reportBranding.get() }); }
export const useUpdateReportBranding = m((d) => platformApi.reportBranding.update(d), ["report-branding"], "Branding saved.");

// ── S-1c: Result Type / Photo (level settings) + subject exclusions ──────────
export function useLevelSettings() { return useQuery<any[]>({ queryKey: ["level-settings"], queryFn: () => platformApi.levelSettings.list() }); }
export const useUpsertLevelSetting = m((d) => platformApi.levelSettings.upsert(d), ["level-settings"], "Saved.");
export function useSubjectExclusions(yearGroup?: string) { return useQuery<any[]>({ queryKey: ["subject-exclusions", yearGroup], queryFn: () => platformApi.subjectExclusions.list(yearGroup) }); }
export const useCreateSubjectExclusion = m((d) => platformApi.subjectExclusions.create(d), ["subject-exclusions"], "Excluded.");
export const useDeleteSubjectExclusion = m((id: string) => platformApi.subjectExclusions.remove(id), ["subject-exclusions"], "Removed.");

// ── S-2: Assessment Group + Assessment ───────────────────────────────────────
export function useAssessmentGroups() { return useQuery<any[]>({ queryKey: ["assessment-groups"], queryFn: () => platformApi.assessmentGroups.list() }); }
export const useCreateAssessmentGroup = m((d) => platformApi.assessmentGroups.create(d), ["assessment-groups"], "Group added.");
export const useDeleteAssessmentGroup = m((id: string) => platformApi.assessmentGroups.remove(id), ["assessment-groups"], "Removed.");
export function useAssessments(termId?: string) { return useQuery<any[]>({ queryKey: ["assessments", termId], queryFn: () => platformApi.assessments.list(termId) }); }
export const useCreateAssessment = m((d) => platformApi.assessments.create(d), ["assessments"], "Assessment added.");
export const useDeleteAssessment = m((id: string) => platformApi.assessments.remove(id), ["assessments"], "Removed.");
export const useBootstrapAssessments = m(() => platformApi.assessments.bootstrap(), ["assessments"], "Seeded Fairview assessment set.");

// ── S-3: Cumulative engine ───────────────────────────────────────────────────
export function useCumulatives(termId?: string) { return useQuery<any[]>({ queryKey: ["cumulatives", termId], queryFn: () => platformApi.cumulatives.list(termId) }); }
export const useCreateCumulative = m((d) => platformApi.cumulatives.create(d), ["cumulatives"], "Cumulative added.");
export const useDeleteCumulative = m((id: string) => platformApi.cumulatives.remove(id), ["cumulatives"], "Removed.");
export const useBootstrapCumulatives = m(() => platformApi.cumulatives.bootstrap(), ["cumulatives"], "Seeded cumulative columns.");

// ── S-4a: Report Entry (assessment scores) ───────────────────────────────────
export function useReportEntryGrid(p: { class_id: string; subject_id: string; term_id: string }) {
  return useQuery<any>({
    queryKey: ["report-entry", p],
    queryFn: () => platformApi.reportEntry.grid(p),
    enabled: !!p.class_id && !!p.subject_id && !!p.term_id,
  });
}
export const useSaveReportEntry = m((d) => platformApi.reportEntry.save(d), ["report-entry"], "Scores saved.");

// ── S-4b: Broadsheet ─────────────────────────────────────────────────────────
export function useBroadsheet(p: { class_id: string; term_id: string; sub_term_id: string }) {
  return useQuery<any>({
    queryKey: ["broadsheet", p],
    queryFn: () => platformApi.broadsheet(p),
    enabled: !!p.class_id && !!p.term_id && !!p.sub_term_id,
  });
}
