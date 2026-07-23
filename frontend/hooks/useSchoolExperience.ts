"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  classroomApi,
  cbtApi,
  behaviourApi,
  feedbackApi,
  clubsApi,
  journalsApi,
  tuckshopApi,
  schoolApi,
  meApi,
} from "@/lib/api";

// ── /me — School Context ─────────────────────────────────────────────────────

export function useSchoolContext() {
  return useQuery({
    queryKey: ["me", "school-context"],
    queryFn: () => meApi.schoolContext(),
    staleTime: 5 * 60_000,
  });
}

// ── eClassroom: Assignments ──────────────────────────────────────────────────

export function useAssignments(params?: { class_id?: string; subject_id?: string; teacher_id?: string; status?: string; for_me?: boolean; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["assignments", params],
    queryFn: () => classroomApi.assignments.list(params),
  });
}

export function useAssignment(id: string) {
  return useQuery({
    queryKey: ["assignments", id],
    queryFn: () => classroomApi.assignments.get(id),
    enabled: !!id,
  });
}

export function useCreateAssignment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => classroomApi.assignments.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      toast.success("Assignment published.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to publish assignment."),
  });
}

export function useUpdateAssignment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => classroomApi.assignments.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      toast.success("Assignment updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update assignment."),
  });
}

export function useDeleteAssignment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => classroomApi.assignments.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      toast.success("Assignment removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove assignment."),
  });
}

// ── eClassroom: Submissions ──────────────────────────────────────────────────

export function useAssignmentSubmissions(assignment_id: string) {
  return useQuery({
    queryKey: ["submissions", assignment_id],
    queryFn: () => classroomApi.assignments.submissions(assignment_id),
    enabled: !!assignment_id,
  });
}

export function useSubmitAssignment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => classroomApi.submissions.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["submissions"] });
      qc.invalidateQueries({ queryKey: ["my-submissions"] });
      toast.success("Submission received.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit."),
  });
}

export function useGradeSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, score, feedback }: { id: string; score: number; feedback?: string }) =>
      classroomApi.submissions.grade(id, { score, feedback }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["submissions"] });
      toast.success("Submission graded.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to grade."),
  });
}

export function useMySubmissions(student_id: string) {
  return useQuery({
    queryKey: ["my-submissions", student_id],
    queryFn: () => classroomApi.submissions.mine(student_id),
    enabled: !!student_id,
  });
}

// ── eClassroom: Reflections ──────────────────────────────────────────────────

export function useReflections(params?: { student_id?: string; for_me?: boolean }) {
  return useQuery({
    queryKey: ["reflections", params],
    queryFn: () => classroomApi.reflections.list(params),
  });
}

export function useCreateReflection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => classroomApi.reflections.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reflections"] });
      toast.success("Reflection saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save reflection."),
  });
}

export function useCommentReflection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, teacher_comment }: { id: string; teacher_comment: string }) =>
      classroomApi.reflections.comment(id, teacher_comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reflections"] });
      toast.success("Comment added.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to comment."),
  });
}

// ── CBT: Exams ───────────────────────────────────────────────────────────────

export function useCBTExams(params?: { class_id?: string; status?: string; for_me?: boolean; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["cbt-exams", params],
    queryFn: () => cbtApi.exams.list(params),
  });
}

export function useCBTExam(id: string) {
  return useQuery({
    queryKey: ["cbt-exams", id],
    queryFn: () => cbtApi.exams.get(id),
    enabled: !!id,
  });
}

export function useCreateCBTExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => cbtApi.exams.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cbt-exams"] });
      toast.success("Exam created.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create exam."),
  });
}

export function useUpdateCBTExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => cbtApi.exams.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cbt-exams"] });
      toast.success("Exam updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update exam."),
  });
}

export function useDeleteCBTExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cbtApi.exams.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cbt-exams"] });
      toast.success("Exam removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove exam."),
  });
}

// ── CBT: Questions ───────────────────────────────────────────────────────────

export function useCBTQuestions(exam_id: string, include_answers = false) {
  return useQuery({
    queryKey: ["cbt-questions", exam_id, include_answers],
    queryFn: () => cbtApi.questions.list(exam_id, include_answers),
    enabled: !!exam_id,
  });
}

export function useAddCBTQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ exam_id, data }: { exam_id: string; data: object }) => cbtApi.questions.add(exam_id, data),
    onSuccess: (_, { exam_id }) => {
      qc.invalidateQueries({ queryKey: ["cbt-questions", exam_id] });
      qc.invalidateQueries({ queryKey: ["cbt-exams"] });
      toast.success("Question added.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add question."),
  });
}

export function useDeleteCBTQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cbtApi.questions.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cbt-questions"] });
      qc.invalidateQueries({ queryKey: ["cbt-exams"] });
      toast.success("Question removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove question."),
  });
}

// ── CBT: Results (manager / remark) ──────────────────────────────────────────

export function useExamResults(exam_id: string | null) {
  return useQuery({
    queryKey: ["cbt-results", exam_id],
    queryFn: () => cbtApi.results.get(exam_id as string),
    enabled: !!exam_id,
  });
}

export function useAttemptReview(attempt_id: string | null) {
  return useQuery({
    queryKey: ["cbt-review", attempt_id],
    queryFn: () => cbtApi.attempts.review(attempt_id as string),
    enabled: !!attempt_id,
  });
}

export function useRemarkAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ attempt_id, items }: { attempt_id: string; items: Array<{ answer_id: string; points_awarded: number }> }) =>
      cbtApi.attempts.remark(attempt_id, items),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: ["cbt-results"] });
      qc.invalidateQueries({ queryKey: ["cbt-review", vars.attempt_id] });
      toast.success("Marks saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save marks."),
  });
}

// ── CBT: Reset / Interventions / Settings (Phase C) ──────────────────────────

export function useResetAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (attempt_id: string) => cbtApi.attempts.reset(attempt_id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-results"] }); toast.success("Attempt reset — the student can retake."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to reset attempt."),
  });
}

export function usePublishResults() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ exam_id, publish }: { exam_id: string; publish: boolean }) =>
      publish ? cbtApi.results.publish(exam_id) : cbtApi.results.unpublish(exam_id),
    onSuccess: (d: any, v) => {
      qc.invalidateQueries({ queryKey: ["cbt-results"] });
      if (!v.publish) { toast.success("Results unpublished."); return; }
      const gb = d?.gradebook;
      if (gb?.fed > 0) toast.success(`Results published; ${gb.fed} grade(s) sent to the gradebook (draft).`);
      else if (gb?.blocked) toast.success(`Results published to students. Not sent to the gradebook — ${gb.blocked}`);
      else toast.success("Results published to students.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update publish state."),
  });
}

export function useFeedGradebook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (exam_id: string) => cbtApi.results.feedGradebook(exam_id),
    onSuccess: (d: any) => {
      qc.invalidateQueries({ queryKey: ["cbt-results"] });
      toast.success(`${d?.fed ?? 0} grade(s) sent to the gradebook as drafts. Publish them from the gradebook to release to parents.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't send results to the gradebook."),
  });
}

export function useInterventions(params?: { status?: string; student_id?: string; exam_id?: string }) {
  return useQuery({
    queryKey: ["cbt-interventions", params],
    queryFn: () => cbtApi.interventions.list(params),
  });
}

export function useCreateIntervention() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => cbtApi.interventions.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-interventions"] }); toast.success("Flagged for intervention."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to flag."),
  });
}

export function useUpdateIntervention() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => cbtApi.interventions.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-interventions"] }); toast.success("Intervention updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}

export function useCBTSettings() {
  return useQuery({ queryKey: ["cbt-settings"], queryFn: () => cbtApi.settings.get() });
}

export function useUpdateCBTSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => cbtApi.settings.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-settings"] }); toast.success("CBT settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save settings."),
  });
}

// ── CBT: Question Bank ───────────────────────────────────────────────────────

export function useBankItems(params?: { subject_id?: string; topic?: string; difficulty?: string; question_type?: string; search?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["cbt-bank", params],
    queryFn: () => cbtApi.bank.list(params),
  });
}

export function useCreateBankItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => cbtApi.bank.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-bank"] }); toast.success("Question added to bank."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add question."),
  });
}

export function useUpdateBankItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => cbtApi.bank.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-bank"] }); toast.success("Question updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update question."),
  });
}

export function useDeleteBankItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cbtApi.bank.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cbt-bank"] }); toast.success("Question removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove question."),
  });
}

export function useImportBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => cbtApi.bank.import(file),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ["cbt-bank"] });
      const errs = res?.errors?.length ? ` (${res.errors.length} row${res.errors.length === 1 ? "" : "s"} skipped)` : "";
      toast.success(`Imported ${res?.imported ?? 0} question${(res?.imported ?? 0) === 1 ? "" : "s"}${errs}.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Import failed."),
  });
}

export function useAddFromBank() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ exam_id, question_ids }: { exam_id: string; question_ids: string[] }) => cbtApi.questions.addFromBank(exam_id, question_ids),
    onSuccess: (res: any, { exam_id }) => {
      qc.invalidateQueries({ queryKey: ["cbt-questions", exam_id] });
      qc.invalidateQueries({ queryKey: ["cbt-exams"] });
      toast.success(`Added ${res?.added ?? 0} question${(res?.added ?? 0) === 1 ? "" : "s"} from the bank.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add from bank."),
  });
}

// ── CBT: Attempts ────────────────────────────────────────────────────────────

export function useCBTAttempts(params?: { exam_id?: string; student_id?: string }) {
  return useQuery({
    queryKey: ["cbt-attempts", params],
    queryFn: () => cbtApi.attempts.list(params),
  });
}

export function useCBTAttempt(attempt_id: string) {
  return useQuery({
    queryKey: ["cbt-attempts", attempt_id],
    queryFn: () => cbtApi.attempts.get(attempt_id),
    enabled: !!attempt_id,
  });
}

export function useStartCBTAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ exam_id, student_id }: { exam_id: string; student_id: string }) =>
      cbtApi.attempts.start(exam_id, student_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cbt-attempts"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to start attempt."),
  });
}

export function useSubmitCBTAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ attempt_id, answers }: { attempt_id: string; answers: Array<{ question_id: string; answer_text: string }> }) =>
      cbtApi.attempts.submit(attempt_id, answers),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cbt-attempts"] });
      toast.success("Exam submitted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit attempt."),
  });
}

// ── Behaviour ────────────────────────────────────────────────────────────────

export function useBehaviourRecords(params?: { student_id?: string; type?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["behaviour", params],
    queryFn: () => behaviourApi.list(params),
  });
}

export function useCreateBehaviourRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => behaviourApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["behaviour"] });
      qc.invalidateQueries({ queryKey: ["behaviour-summary"] });
      toast.success("Behaviour record added.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add record."),
  });
}

export function useDeleteBehaviourRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => behaviourApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["behaviour"] });
      qc.invalidateQueries({ queryKey: ["behaviour-summary"] });
      toast.success("Record removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove record."),
  });
}

export function useBehaviourSummary(student_id: string) {
  return useQuery({
    queryKey: ["behaviour-summary", student_id],
    queryFn: () => behaviourApi.studentSummary(student_id),
    enabled: !!student_id,
    staleTime: 60_000,
  });
}

export function useBehaviourSchoolSummary(days = 30) {
  return useQuery({
    queryKey: ["behaviour-school-summary", days],
    queryFn: () => behaviourApi.schoolSummary(days),
    staleTime: 60_000,
  });
}

// ── Feedback ─────────────────────────────────────────────────────────────────

export function useFeedbackList(params?: { mine?: boolean; category?: string; resolved?: boolean; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["feedback", params],
    queryFn: () => feedbackApi.list(params),
  });
}

export function useSubmitFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => feedbackApi.submit(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
      toast.success("Feedback submitted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit feedback."),
  });
}

export function useResolveFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, admin_response, is_resolved }: { id: string; admin_response: string; is_resolved?: boolean }) =>
      feedbackApi.resolve(id, { admin_response, is_resolved }),
    // Optimistic update: flip the resolved badge the moment an admin responds.
    // Rolls back on error so the UI never lies about the resolution state.
    onMutate: async ({ id, admin_response, is_resolved = true }) => {
      await qc.cancelQueries({ queryKey: ["feedback"] });
      const snapshots = qc.getQueriesData({ queryKey: ["feedback"] });
      qc.setQueriesData({ queryKey: ["feedback"] }, (old: any) => {
        if (!old?.items) return old;
        return {
          ...old,
          items: old.items.map((f: any) =>
            f.id === id ? { ...f, admin_response, is_resolved, __optimistic: true } : f
          ),
        };
      });
      return { snapshots };
    },
    onError: (e: any, _vars, ctx) => {
      ctx?.snapshots?.forEach(([key, data]: [any, any]) => qc.setQueryData(key, data));
      toast.error(e?.response?.data?.detail || "Failed to resolve feedback.");
    },
    onSuccess: () => {
      toast.success("Feedback resolved.");
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
  });
}

// ── Clubs ────────────────────────────────────────────────────────────────────

export function useClubs(params?: { is_active?: boolean; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["clubs", params],
    queryFn: () => clubsApi.list(params),
  });
}

export function useClub(id: string) {
  return useQuery({
    queryKey: ["clubs", id],
    queryFn: () => clubsApi.get(id),
    enabled: !!id,
  });
}

export function useClubMembers(club_id: string) {
  return useQuery({
    queryKey: ["club-members", club_id],
    queryFn: () => clubsApi.members(club_id),
    enabled: !!club_id,
  });
}

export function useCreateClub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => clubsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clubs"] });
      toast.success("Club created.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create club."),
  });
}

export function useUpdateClub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => clubsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clubs"] });
      toast.success("Club updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update club."),
  });
}

export function useDeleteClub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clubsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clubs"] });
      toast.success("Club deleted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete club."),
  });
}

export function useJoinClub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ club_id, student_id, role }: { club_id: string; student_id: string; role?: string }) =>
      clubsApi.join(club_id, { student_id, role }),
    onSuccess: (_, { club_id }) => {
      qc.invalidateQueries({ queryKey: ["clubs"] });
      qc.invalidateQueries({ queryKey: ["club-members", club_id] });
      toast.success("Member added.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add member."),
  });
}

export function useLeaveClub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (membership_id: string) => clubsApi.leave(membership_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clubs"] });
      qc.invalidateQueries({ queryKey: ["club-members"] });
      toast.success("Member removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove member."),
  });
}

// ── Photo Journals ───────────────────────────────────────────────────────────

export function useJournals(params?: { class_id?: string; club_id?: string; tag?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["journals", params],
    queryFn: () => journalsApi.list(params),
  });
}

export function useCreateJournal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => journalsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["journals"] });
      toast.success("Journal posted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to post journal."),
  });
}

export function useDeleteJournal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => journalsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["journals"] });
      toast.success("Journal removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove journal."),
  });
}

// ── Weekly Remarks ───────────────────────────────────────────────────────────

export function useWeeklyRemarks(params?: { student_id?: string; week_start?: string; for_me?: boolean }) {
  return useQuery({
    queryKey: ["remarks", params],
    queryFn: () => journalsApi.remarks.list(params),
  });
}

export function useCreateRemark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => journalsApi.remarks.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remarks"] });
      toast.success("Remark saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save remark."),
  });
}

export function useDeleteRemark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => journalsApi.remarks.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remarks"] });
      toast.success("Remark removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove remark."),
  });
}

// ── Tuckshop ─────────────────────────────────────────────────────────────────

export function useTuckshopProducts(params?: { category?: string; is_active?: boolean; low_stock?: boolean; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["tuckshop-products", params],
    queryFn: () => tuckshopApi.products.list(params),
  });
}

export function useCreateTuckshopProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => tuckshopApi.products.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tuckshop-products"] });
      toast.success("Product added.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add product."),
  });
}

export function useUpdateTuckshopProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => tuckshopApi.products.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tuckshop-products"] });
      toast.success("Product updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update product."),
  });
}

export function useDeleteTuckshopProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tuckshopApi.products.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tuckshop-products"] });
      toast.success("Product removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove product."),
  });
}

export function useTuckshopPurchases(params?: { student_id?: string; product_id?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["tuckshop-purchases", params],
    queryFn: () => tuckshopApi.purchases.list(params),
  });
}

export function useTuckshopSalesSummary(date?: string) {
  return useQuery({
    queryKey: ["tuckshop-sales-summary", date ?? "today"],
    queryFn: () => tuckshopApi.salesSummary(date),
    staleTime: 30_000,
  });
}

export function useRecordPurchase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => tuckshopApi.purchases.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tuckshop-purchases"] });
      qc.invalidateQueries({ queryKey: ["tuckshop-products"] });
      qc.invalidateQueries({ queryKey: ["tuckshop-sales-summary"] });
      toast.success("Sale recorded.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record sale."),
  });
}

// ── Student Attendance History ───────────────────────────────────────────────

export function useStudentAttendanceHistory(student_id: string, start_date?: string, end_date?: string) {
  return useQuery({
    queryKey: ["student-attendance", student_id, start_date, end_date],
    queryFn: () => (schoolApi.attendance as any).studentHistory(student_id, start_date, end_date),
    enabled: !!student_id,
  });
}

// ── Manage Clubs (settings / grades / coordinators / deadlines) ───────────────

export function useClubSettings() {
  return useQuery({ queryKey: ["club-settings"], queryFn: () => clubsApi.settings.get() });
}
export function useUpdateClubSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => clubsApi.settings.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-settings"] }); toast.success("Club settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save settings."),
  });
}
export function useClubGrades() {
  return useQuery({ queryKey: ["club-grades"], queryFn: () => clubsApi.grades.list() });
}
export function useCreateClubGrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => clubsApi.grades.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-grades"] }); toast.success("Grade added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add grade."),
  });
}
export function useUpdateClubGrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => clubsApi.grades.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-grades"] }); toast.success("Grade updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update grade."),
  });
}
export function useDeleteClubGrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clubsApi.grades.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-grades"] }); toast.success("Grade removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove grade."),
  });
}
export function useClubCoordinators() {
  return useQuery({ queryKey: ["club-coordinators"], queryFn: () => clubsApi.coordinators.list() });
}
export function useCreateClubCoordinator() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => clubsApi.coordinators.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-coordinators"] }); toast.success("Coordinator assigned."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to assign coordinator."),
  });
}
export function useDeleteClubCoordinator() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clubsApi.coordinators.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-coordinators"] }); toast.success("Coordinator removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove coordinator."),
  });
}
export function useClubDeadlines() {
  return useQuery({ queryKey: ["club-deadlines"], queryFn: () => clubsApi.deadlines.list() });
}
export function useCreateClubDeadline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => clubsApi.deadlines.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-deadlines"] }); toast.success("Deadline added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add deadline."),
  });
}
export function useDeleteClubDeadline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clubsApi.deadlines.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-deadlines"] }); toast.success("Deadline removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove deadline."),
  });
}

// ── Club Membership List + Enrollment ─────────────────────────────────────────

export function useClubMembershipSummary(params: { academic_year?: string; term?: string }) {
  return useQuery({ queryKey: ["club-membership-summary", params.academic_year, params.term], queryFn: () => clubsApi.membershipSummary(params) });
}
export function useClubMembersByTerm(clubId: string | null, params: { academic_year?: string; term?: string }) {
  return useQuery({ queryKey: ["club-members", clubId, params.academic_year, params.term], queryFn: () => clubsApi.members(clubId as string, params), enabled: !!clubId });
}
export function useUpdateMembershipStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => clubsApi.updateMembership(id, { status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-members"] }); qc.invalidateQueries({ queryKey: ["club-membership-summary"] }); toast.success("Membership updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update membership."),
  });
}
export function useEnrollmentCandidates(clubId: string | null, params: { academic_year?: string; term?: string; class_id?: string }) {
  return useQuery({
    queryKey: ["club-enroll-candidates", clubId, params.academic_year, params.term, params.class_id],
    queryFn: () => clubsApi.enrollmentCandidates(clubId as string, params),
    enabled: !!clubId,
  });
}
export function useEnrollStudents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => clubsApi.enroll(id, data),
    onSuccess: (r: any) => { qc.invalidateQueries({ queryKey: ["club-enroll-candidates"] }); qc.invalidateQueries({ queryKey: ["club-membership-summary"] }); toast.success(`Enrolled ${r?.enrolled ?? 0} student(s)${r?.skipped ? `, ${r.skipped} skipped` : ""}.`); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to enroll."),
  });
}
export function useUnenrollMembership() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (membershipId: string) => clubsApi.leave(membershipId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-enroll-candidates"] }); qc.invalidateQueries({ queryKey: ["club-membership-summary"] }); toast.success("Removed from club."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Club Assessment ───────────────────────────────────────────────────────────

export function useClubAssessments(clubId: string | null, params: { academic_year?: string; term?: string }) {
  return useQuery({
    queryKey: ["club-assessments", clubId, params.academic_year, params.term],
    queryFn: () => clubsApi.assessments.get(clubId as string, params),
    enabled: !!clubId,
  });
}
export function useSaveClubAssessments() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => clubsApi.assessments.save(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["club-assessments"] }); toast.success("Assessment saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save assessment."),
  });
}
