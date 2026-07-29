"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { pastoralApi, medicalApi } from "@/lib/api";
import type {
  Hostel, BoardingAllocation, ExeatRequest, MentorReport, StudentMedicalRecord, Paginated,
} from "@/types";

// ── Hostels + Boarding ──────────────────────────────────────────────────────────

export function useHostels() {
  return useQuery<Paginated<Hostel>>({ queryKey: ["hostels"], queryFn: () => pastoralApi.hostels.list() });
}
export function useHostelAllocations(hostelId: string | null) {
  return useQuery<BoardingAllocation[]>({
    queryKey: ["hostels", hostelId, "allocations"],
    queryFn: () => pastoralApi.hostels.allocations(hostelId as string),
    enabled: !!hostelId,
  });
}
export function useCreateHostel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.hostels.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Hostel saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save hostel."),
  });
}
export function useUpdateHostel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.hostels.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Hostel updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteHostel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.hostels.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Hostel removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
export function useAllocateBoarder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.allocations.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Boarder allocated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to allocate."),
  });
}
export function useDeallocateBoarder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.allocations.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Boarder removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Exeat ────────────────────────────────────────────────────────────────────

export function useExeats(params?: { status?: string }) {
  return useQuery<Paginated<ExeatRequest>>({ queryKey: ["exeats", params], queryFn: () => pastoralApi.exeats.list(params) });
}
export function useCreateExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.exeats.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat requested."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to request exeat."),
  });
}
export function useUpdateExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.exeats.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useApproveExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: object }) => pastoralApi.exeats.approve(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat approved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "You can’t authorise this exeat."),
  });
}
export function useRejectExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: object }) => pastoralApi.exeats.reject(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat rejected."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "You can’t authorise this exeat."),
  });
}
export function useReturnExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.exeats.markReturned(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Marked returned."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}

// ── Mentor Reports ────────────────────────────────────────────────────────────

export function useMentorReports(params?: { student_id?: string; mentor_id?: string }) {
  return useQuery<Paginated<MentorReport>>({ queryKey: ["mentor-reports", params], queryFn: () => pastoralApi.mentorReports.list(params) });
}
export function useCreateMentorReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.mentorReports.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-reports"] }); toast.success("Report saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save report."),
  });
}
export function useUpdateMentorReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.mentorReports.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-reports"] }); toast.success("Report updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteMentorReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.mentorReports.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-reports"] }); toast.success("Report removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Medicals (confidential) ───────────────────────────────────────────────────

export function useMedicalRecords(params?: { student_id?: string; record_type?: string }) {
  return useQuery<Paginated<StudentMedicalRecord>>({ queryKey: ["medical", params], queryFn: () => medicalApi.list(params) });
}
export function useCreateMedicalRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => medicalApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medical"] }); toast.success("Record saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save record."),
  });
}
export function useUpdateMedicalRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => medicalApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medical"] }); toast.success("Record updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteMedicalRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => medicalApi.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medical"] }); toast.success("Record removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Pastoral Setup: settings ────────────────────────────────────────────────────

export function usePastoralSettings() {
  return useQuery({ queryKey: ["pastoral-settings"], queryFn: () => pastoralApi.settings.get() });
}

export function useUpdatePastoralSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.settings.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pastoral-settings"] }); toast.success("Settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save settings."),
  });
}

// ── Batch B: House Masters / Weeks / Pastoral Students ──────────────────────────

export function useHouseMasters(houseId?: string) {
  return useQuery({ queryKey: ["house-masters", houseId ?? "all"], queryFn: () => pastoralApi.houseMasters.list(houseId) });
}
export function useAddHouseMaster() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { house_id: string; user_id: string }) => pastoralApi.houseMasters.add(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["house-masters"] }); toast.success("House master added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add."),
  });
}
export function useRemoveHouseMaster() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.houseMasters.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["house-masters"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

export function useHouseWeeks() {
  return useQuery({ queryKey: ["house-weeks"], queryFn: () => pastoralApi.houseWeeks.list() });
}
export function useCreateHouseWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.houseWeeks.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["house-weeks"] }); toast.success("Week added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useUpdateHouseWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.houseWeeks.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["house-weeks"] }); toast.success("Updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useDeleteHouseWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.houseWeeks.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["house-weeks"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}

export function usePastoralStudents(params?: { section?: string; class_id?: string; house?: string; search?: string }) {
  return useQuery({ queryKey: ["pastoral-students", params], queryFn: () => pastoralApi.students.list(params) });
}
export function useAssignPastoralStudent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, data }: { studentId: string; data: object }) => pastoralApi.students.assign(studentId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pastoral-students"] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to assign."),
  });
}
export function useBulkAssignPastoralStudents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.students.bulkAssign(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pastoral-students"] }); toast.success("Applied."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useSyncPastoralStudents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => pastoralApi.students.sync(),
    onSuccess: (r: any) => { qc.invalidateQueries({ queryKey: ["pastoral-students"] }); toast.success(`Synced ${r?.synced ?? 0} student(s).`); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Sync failed."),
  });
}

// ── Batch C: Point System / Award System / Points Analysis ──────────────────────

function crud(resource: "pointTypes" | "awardTypes" | "hostelLifeGrades" | "hostelCommentBank" | "sanctionGroups" | "disciplinaryActions" | "leadershipRoles" | "pastoralHeads" | "remarkBank", key: string) {
  return {
    useList: () => useQuery({ queryKey: [key], queryFn: () => (pastoralApi as any)[resource].list() }),
    useCreate: () => { const qc = useQueryClient(); return useMutation({ mutationFn: (d: object) => (pastoralApi as any)[resource].create(d), onSuccess: () => { qc.invalidateQueries({ queryKey: [key] }); toast.success("Added."); }, onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed.") }); },
    useUpdate: () => { const qc = useQueryClient(); return useMutation({ mutationFn: (v: { id: string; data: object }) => (pastoralApi as any)[resource].update(v.id, v.data), onSuccess: () => { qc.invalidateQueries({ queryKey: [key] }); toast.success("Updated."); }, onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed.") }); },
    useDelete: () => { const qc = useQueryClient(); return useMutation({ mutationFn: (id: string) => (pastoralApi as any)[resource].remove(id), onSuccess: () => { qc.invalidateQueries({ queryKey: [key] }); toast.success("Removed."); }, onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed.") }); },
  };
}
const _pt = crud("pointTypes", "point-types");
const _at = crud("awardTypes", "award-types");
export const usePointTypes = _pt.useList;
export const useCreatePointType = _pt.useCreate;
export const useUpdatePointType = _pt.useUpdate;
export const useDeletePointType = _pt.useDelete;
export const useAwardTypes = _at.useList;
export const useCreateAwardType = _at.useCreate;
export const useUpdateAwardType = _at.useUpdate;
export const useDeleteAwardType = _at.useDelete;

export function useAddPoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.points.add(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pastoral-points"] }); qc.invalidateQueries({ queryKey: ["points-analysis"] }); toast.success("Point recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record point."),
  });
}
export function usePointEntries(params?: { student_id?: string; term?: string }) {
  return useQuery({ queryKey: ["pastoral-points", params], queryFn: () => pastoralApi.points.list(params) });
}

// ── Batch D-1: Hostel Setup (managers / life grades / comment bank) + Students ──

const _hg = crud("hostelLifeGrades", "hostel-life-grades");
const _cb = crud("hostelCommentBank", "hostel-comment-bank");
export const useHostelLifeGrades = _hg.useList;
export const useCreateHostelLifeGrade = _hg.useCreate;
export const useUpdateHostelLifeGrade = _hg.useUpdate;
export const useDeleteHostelLifeGrade = _hg.useDelete;
export const useHostelCommentBank = _cb.useList;
export const useCreateHostelComment = _cb.useCreate;
export const useUpdateHostelComment = _cb.useUpdate;
export const useDeleteHostelComment = _cb.useDelete;

export function useHostelManagers(hostelId?: string) {
  return useQuery({ queryKey: ["hostel-managers", hostelId], queryFn: () => pastoralApi.hostelManagers.list(hostelId), enabled: !!hostelId });
}
export function useAddHostelManager() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { hostel_id: string; user_id: string }) => pastoralApi.hostelManagers.add(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-managers"] }); toast.success("Manager added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add manager."),
  });
}
export function useRemoveHostelManager() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.hostelManagers.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-managers"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useHostelStudents(params?: { hostel_id?: string; search?: string }) {
  return useQuery({ queryKey: ["hostel-students", params], queryFn: () => pastoralApi.hostelStudents.list(params) });
}
export function useImportHostelStudents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) => pastoralApi.hostelStudents.import(formData),
    onSuccess: (r: any) => {
      qc.invalidateQueries({ queryKey: ["hostel-students"] });
      toast.success(`Imported ${r?.imported ?? 0} boarder(s).${r?.errors?.length ? ` ${r.errors.length} skipped.` : ""}`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Import failed."),
  });
}

// ── Batch D-2: hostel life comments + Result View + reports ──────────────────

export function useHostelLifeComments(params?: { student_id?: string; hostel_id?: string; term?: string }) {
  return useQuery({ queryKey: ["hostel-life-comments", params], queryFn: () => pastoralApi.hostelLifeComments.list(params) });
}
export function useAddHostelLifeComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.hostelLifeComments.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-life-comments"] }); qc.invalidateQueries({ queryKey: ["hostel-results"] }); toast.success("Comment recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
export function useDeleteHostelLifeComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.hostelLifeComments.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-life-comments"] }); qc.invalidateQueries({ queryKey: ["hostel-results"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useHostelResults(params?: { hostel_id?: string; term?: string }) {
  return useQuery({ queryKey: ["hostel-results", params], queryFn: () => pastoralApi.hostelResults.list(params) });
}
export function useHostelReports(params?: { report_type?: string; hostel_id?: string }) {
  return useQuery({ queryKey: ["hostel-reports", params], queryFn: () => pastoralApi.hostelReports.list(params) });
}
export function useAddHostelReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.hostelReports.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-reports"] }); toast.success("Report saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save."),
  });
}
export function useUpdateHostelReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; data: object }) => pastoralApi.hostelReports.update(v.id, v.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-reports"] }); toast.success("Updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useDeleteHostelReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.hostelReports.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostel-reports"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}

// ── Batch E: Discipline ──────────────────────────────────────────────────────

const _sanctionGroups = crud("sanctionGroups", "sanction-groups");
const _discActions = crud("disciplinaryActions", "disciplinary-actions");
export const useSanctionGroups = _sanctionGroups.useList;
export const useCreateSanctionGroup = _sanctionGroups.useCreate;
export const useUpdateSanctionGroup = _sanctionGroups.useUpdate;
export const useDeleteSanctionGroup = _sanctionGroups.useDelete;
export const useDisciplinaryActions = _discActions.useList;
export const useCreateDisciplinaryAction = _discActions.useCreate;
export const useUpdateDisciplinaryAction = _discActions.useUpdate;
export const useDeleteDisciplinaryAction = _discActions.useDelete;

export function useCommittees() {
  return useQuery({ queryKey: ["committees"], queryFn: () => pastoralApi.committees.list() });
}
function committeeMut<TArgs>(fn: (a: TArgs) => Promise<any>, msg: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["committees"] }); if (msg) toast.success(msg); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useCreateCommittee() { return committeeMut((d: object) => pastoralApi.committees.create(d), "Committee created."); }
export function useUpdateCommittee() { return committeeMut((v: { id: string; data: object }) => pastoralApi.committees.update(v.id, v.data), "Updated."); }
export function useDeleteCommittee() { return committeeMut((id: string) => pastoralApi.committees.remove(id), "Removed."); }
export function useAddCommitteeMember() { return committeeMut((v: { id: string; data: { user_id: string; role_label?: string | null } }) => pastoralApi.committees.addMember(v.id, v.data), "Member added."); }
export function useRemoveCommitteeMember() { return committeeMut((memberId: string) => pastoralApi.committees.removeMember(memberId), "Removed."); }

export function useDisciplinaryCases(params?: { student_id?: string; status?: string }) {
  return useQuery({ queryKey: ["disciplinary-cases", params], queryFn: () => pastoralApi.disciplinaryCases.list(params) });
}
function caseMut<TArgs>(fn: (a: TArgs) => Promise<any>, msg: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["disciplinary-cases"] }); if (msg) toast.success(msg); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useCreateDisciplinaryCase() { return caseMut((d: object) => pastoralApi.disciplinaryCases.create(d), "Case recorded."); }
export function useUpdateDisciplinaryCase() { return caseMut((v: { id: string; data: object }) => pastoralApi.disciplinaryCases.update(v.id, v.data), "Updated."); }
export function useDeleteDisciplinaryCase() { return caseMut((id: string) => pastoralApi.disciplinaryCases.remove(id), "Removed."); }

// ── Batch F-1: Leadership Roles + Pastoral Heads + Head Dashboard ─────────────

const _leadershipRoles = crud("leadershipRoles", "leadership-roles");
const _pastoralHeads = crud("pastoralHeads", "pastoral-heads");
export const useLeadershipRoles = _leadershipRoles.useList;
export const useCreateLeadershipRole = _leadershipRoles.useCreate;
export const useUpdateLeadershipRole = _leadershipRoles.useUpdate;
export const useDeleteLeadershipRole = _leadershipRoles.useDelete;
export const usePastoralHeads = _pastoralHeads.useList;
export const useCreatePastoralHead = _pastoralHeads.useCreate;
export const useUpdatePastoralHead = _pastoralHeads.useUpdate;
export const useDeletePastoralHead = _pastoralHeads.useDelete;

export function useHeadDashboard() {
  return useQuery({ queryKey: ["head-dashboard"], queryFn: () => pastoralApi.headDashboard() });
}

// ── Batch F-2: Roll Call + Report Setup + Pastoral Report/Remarks ─────────────

const _remarkBank = crud("remarkBank", "remark-bank");
export const useRemarkBank = _remarkBank.useList;
export const useCreateRemark = _remarkBank.useCreate;
export const useUpdateRemark = _remarkBank.useUpdate;
export const useDeleteRemark = _remarkBank.useDelete;

export function useRollCall(params: { hostel_id: string; roll_date: string; session: string }) {
  return useQuery({
    queryKey: ["roll-call", params],
    queryFn: () => pastoralApi.rollCall.get(params),
    enabled: !!params.hostel_id && !!params.roll_date,
  });
}
export function useMarkRollCall() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.rollCall.mark(data),
    onSuccess: (r: any) => { qc.invalidateQueries({ queryKey: ["roll-call"] }); toast.success(`Saved ${r?.saved ?? 0} mark(s).`); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save roll call."),
  });
}
export function usePastoralRemarks(params?: { student_id?: string; term?: string }) {
  return useQuery({ queryKey: ["pastoral-remarks", params], queryFn: () => pastoralApi.pastoralRemarks.list(params) });
}
export function useAddPastoralRemark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.pastoralRemarks.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pastoral-remarks"] }); qc.invalidateQueries({ queryKey: ["pastoral-report"] }); toast.success("Remark saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function useDeletePastoralRemark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.pastoralRemarks.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pastoral-remarks"] }); qc.invalidateQueries({ queryKey: ["pastoral-report"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed."),
  });
}
export function usePastoralReport(params: { student_id: string; term?: string }) {
  return useQuery({
    queryKey: ["pastoral-report", params],
    queryFn: () => pastoralApi.pastoralReport(params),
    enabled: !!params.student_id,
  });
}
export function usePointsAnalysis(params?: { section?: string; house?: string }) {
  return useQuery({ queryKey: ["points-analysis", params], queryFn: () => pastoralApi.points.analysis(params) });
}
