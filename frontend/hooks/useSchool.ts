"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { schoolApi } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/utils";

// ── Students ─────────────────────────────────────────────────────────────────

export function useStudents(params?: { page?: number; page_size?: number; search?: string; class_id?: string; section_id?: string; status?: string }) {
  return useQuery({
    queryKey: ["students", params],
    queryFn: () => schoolApi.students.list(params),
  });
}

export function useStudent(id: string) {
  return useQuery({
    queryKey: ["students", id],
    queryFn: () => schoolApi.students.get(id),
    enabled: !!id,
  });
}

export function useCreateStudent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.students.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Student added successfully.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add student."),
  });
}

export function useUpdateStudent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.students.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Student updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update student."),
  });
}

export function useDeleteStudent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.students.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Student removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove student."),
  });
}

// ── Teachers ─────────────────────────────────────────────────────────────────

export function useTeachers(params?: { page?: number; page_size?: number; search?: string; department?: string }) {
  return useQuery({
    queryKey: ["teachers", params],
    queryFn: () => schoolApi.teachers.list(params),
  });
}

export function useTeacher(id: string) {
  return useQuery({
    queryKey: ["teachers", id],
    queryFn: () => schoolApi.teachers.get(id),
    enabled: !!id,
  });
}

export function useCreateTeacher() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.teachers.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teachers"] });
      toast.success("Teacher added successfully.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add teacher."),
  });
}

export function useUpdateTeacher() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.teachers.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teachers"] });
      toast.success("Teacher updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update teacher."),
  });
}

export function useDeleteTeacher() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.teachers.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teachers"] });
      toast.success("Teacher removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove teacher."),
  });
}

// ── Classes ──────────────────────────────────────────────────────────────────

export function useClasses(params?: { page?: number; page_size?: number; search?: string }) {
  return useQuery({
    queryKey: ["classes", params],
    queryFn: () => schoolApi.classes.list(params),
  });
}

export function useCreateClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.classes.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success("Class created.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create class."),
  });
}

export function useUpdateClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.classes.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success("Class updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update class."),
  });
}

export function useDeleteClass() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.classes.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success("Class deleted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete class."),
  });
}

// ── Subjects ─────────────────────────────────────────────────────────────────

export function useSubjects(params?: { page?: number; page_size?: number; search?: string }) {
  return useQuery({
    queryKey: ["subjects", params],
    queryFn: () => schoolApi.subjects.list(params),
  });
}

export function useCreateSubject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.subjects.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subjects"] });
      toast.success("Subject created.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create subject."),
  });
}

export function useUpdateSubject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.subjects.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subjects"] });
      toast.success("Subject updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update subject."),
  });
}

// ── Exams ────────────────────────────────────────────────────────────────────

export function useExams(params?: { page?: number; page_size?: number; class_id?: string; status?: string }) {
  return useQuery({
    queryKey: ["exams", params],
    queryFn: () => schoolApi.exams.list(params),
  });
}

export function useCreateExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.exams.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exams"] });
      toast.success("Exam scheduled.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to schedule exam."),
  });
}

export function useUpdateExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.exams.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exams"] });
      toast.success("Exam updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update exam."),
  });
}

export function useExamResults(examId: string | null) {
  return useQuery({
    queryKey: ["exam-results", examId],
    queryFn: () => schoolApi.exams.results(examId as string),
    enabled: !!examId,
  });
}

export function useSubmitExamResults() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ examId, results }: { examId: string; results: object[] }) =>
      schoolApi.exams.submitResults(examId, results),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["exam-results", vars.examId] });
      qc.invalidateQueries({ queryKey: ["exams"] });
      toast.success("Results saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save results."),
  });
}

// ── Fees ─────────────────────────────────────────────────────────────────────
// Fee records live under /finance/fee-records — see useFeeRecords in useFinance.ts.
// The old /school/fees hooks were removed: that endpoint was never built, and the
// Fee Management page now reads the real StudentFeeRecord data (collections view).

// ── Result publishing ────────────────────────────────────────────────────────

export function useGradePublishStatus(params: { term: string; class_id?: string; exam_id?: string; subject_id?: string }) {
  return useQuery({
    queryKey: ["grade-publish-status", params],
    queryFn: () => schoolApi.grades.publishStatus(params),
    enabled: !!params.term && !!(params.class_id || params.exam_id),
  });
}

export function usePublishGrades() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { term: string; status: "published" | "draft"; class_id?: string; exam_id?: string; subject_id?: string }) =>
      schoolApi.grades.publish(data),
    onSuccess: (res: any, vars) => {
      qc.invalidateQueries({ queryKey: ["grade-publish-status"] });
      const verb = vars.status === "published" ? "Published" : "Unpublished";
      toast.success(`${verb} ${res?.updated ?? 0} grade${(res?.updated ?? 0) === 1 ? "" : "s"}.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update results."),
  });
}

// ── Attendance ───────────────────────────────────────────────────────────────

export function useAttendance(params?: { class_id?: string; date?: string }) {
  return useQuery({
    queryKey: ["attendance", params],
    queryFn: () => schoolApi.attendance.list(params),
  });
}

export function useAttendanceSummary(class_id: string, start_date: string, end_date: string) {
  return useQuery({
    queryKey: ["attendance-summary", class_id, start_date, end_date],
    queryFn: () => schoolApi.attendance.summary(class_id, start_date, end_date),
    enabled: !!class_id && !!start_date && !!end_date,
    staleTime: 60_000,
  });
}

export function useMarkAttendance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ records, date }: { records: object[]; date?: string }) =>
      schoolApi.attendance.mark(records, date),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance"] });
      qc.invalidateQueries({ queryKey: ["attendance-summary"] });
      toast.success("Attendance marked successfully.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to mark attendance."),
  });
}

// ── Attendance Setup (late cutoff + absence reasons) ─────────────────────────
export function useAttendanceSettings() {
  return useQuery({ queryKey: ["attendance-settings"], queryFn: () => schoolApi.attendance.settings.get() });
}
export function useUpdateAttendanceSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.attendance.settings.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["attendance-settings"] }); toast.success("Late cutoff saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save."),
  });
}
export function useAbsenceReasons(activeOnly?: boolean) {
  return useQuery({ queryKey: ["absence-reasons", activeOnly], queryFn: () => schoolApi.attendance.reasons.list(activeOnly) });
}
export function useCreateAbsenceReason() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.attendance.reasons.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["absence-reasons"] }); toast.success("Reason added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add reason."),
  });
}
export function useUpdateAbsenceReason() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.attendance.reasons.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["absence-reasons"] }); toast.success("Reason updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteAbsenceReason() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.attendance.reasons.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["absence-reasons"] }); toast.success("Reason deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete."),
  });
}

// ── Timetable ────────────────────────────────────────────────────────────────

export function useTimetable(params?: { class_id?: string }) {
  return useQuery({
    queryKey: ["timetable", params],
    queryFn: () => schoolApi.timetable.list(params),
    staleTime: 60_000,
  });
}

export function useCreateTimetableSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.timetable.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["timetable"] });
      toast.success("Timetable slot added.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to add timetable slot.")),
  });
}

// ── Ratings ──────────────────────────────────────────────────────────────────

export function useTeacherRatings(params?: { teacher_id?: string; page?: number }) {
  return useQuery({
    queryKey: ["teacher-ratings", params],
    queryFn: () => schoolApi.ratings.list(params),
  });
}

export function useSubmitRating() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.ratings.submit(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teacher-ratings"] });
      toast.success("Rating submitted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit rating."),
  });
}

// ── Lesson Planner (Phase 6.4) ───────────────────────────────────────────────

export interface LessonPlanRow {
  id: string;
  title: string;
  class_id: string;
  class_name: string | null;
  subject_id: string;
  subject_name: string | null;
  teacher_id: string | null;
  teacher_name: string | null;
  lesson_date: string;
  period: number | null;
  duration_minutes: number;
  objectives: string | null;
  activities: string | null;
  materials: string | null;
  homework: string | null;
  notes: string | null;
  status: "draft" | "published";
  created_at: string;
  updated_at: string;
}

export interface LessonPlanListParams {
  class_id?: string;
  subject_id?: string;
  teacher_id?: string;
  start_date?: string;
  end_date?: string;
  status?: "draft" | "published";
  mine?: boolean;
}

export function useLessonPlans(params?: LessonPlanListParams) {
  return useQuery<{ items: LessonPlanRow[]; total: number }>({
    queryKey: ["school", "lessons", params],
    queryFn: () => schoolApi.lessons.list(params),
    staleTime: 30_000,
  });
}

export function useCreateLessonPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.lessons.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["school", "lessons"] });
      toast.success("Lesson plan saved.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to save lesson plan.")),
  });
}

export function useUpdateLessonPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.lessons.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["school", "lessons"] });
      toast.success("Lesson plan updated.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update lesson plan.")),
  });
}

export function usePublishLessonPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.lessons.publish(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["school", "lessons"] });
      toast.success("Lesson plan published.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to publish lesson plan.")),
  });
}

export function useDeleteLessonPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.lessons.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["school", "lessons"] });
      toast.success("Lesson plan removed.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove lesson plan.")),
  });
}

// ── Lesson Planner Setup (categories / settings / supervisors / clone) ────────

export interface LessonCategory { id: string; name: string; org_id: string; }
export interface LessonPlannerSettings { require_approval: boolean; default_duration_minutes: number; allow_backdated: boolean; org_id: string; }
export interface LessonSupervisor { id: string; supervisor_id: string; supervisor_name: string | null; section_id: string | null; section_name: string | null; org_id: string; }

export function useLessonCategories() {
  return useQuery<LessonCategory[]>({ queryKey: ["school", "lesson-categories"], queryFn: () => schoolApi.lessons.categories.list() });
}
function lcMut<V>(fn: (v: V) => Promise<any>, ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { qc.invalidateQueries({ queryKey: ["school", "lesson-categories"] }); qc.invalidateQueries({ queryKey: ["school", "lessons"] }); toast.success(ok); },
      onError: (e) => toast.error(getApiErrorMessage(e, "Action failed.")),
    });
  };
}
export const useCreateLessonCategory = lcMut((d: { name: string }) => schoolApi.lessons.categories.create(d), "Category added.");
export const useUpdateLessonCategory = lcMut((v: { id: string; name: string }) => schoolApi.lessons.categories.update(v.id, { name: v.name }), "Category updated.");
export const useDeleteLessonCategory = lcMut((id: string) => schoolApi.lessons.categories.remove(id), "Category removed.");

export function useLessonPlannerSettings() {
  return useQuery<LessonPlannerSettings>({ queryKey: ["school", "lesson-settings"], queryFn: () => schoolApi.lessons.settings.get() });
}
export function useSaveLessonPlannerSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.lessons.settings.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["school", "lesson-settings"] }); toast.success("Settings saved."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to save settings.")),
  });
}

export function useLessonSupervisors() {
  return useQuery<LessonSupervisor[]>({ queryKey: ["school", "lesson-supervisors"], queryFn: () => schoolApi.lessons.supervisors.list() });
}
export function useAddLessonSupervisor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { supervisor_id: string; section_id?: string | null }) => schoolApi.lessons.supervisors.add(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["school", "lesson-supervisors"] }); toast.success("Supervisor assigned."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to assign supervisor.")),
  });
}
export function useRemoveLessonSupervisor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.lessons.supervisors.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["school", "lesson-supervisors"] }); toast.success("Supervisor removed."); },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove supervisor.")),
  });
}

export function useCloneLessons() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { source_start: string; source_end: string; target_start: string; only_mine?: boolean }) => schoolApi.lessons.clone(data),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ["school", "lessons"] });
      toast.success(`Cloned ${res?.cloned ?? 0} plan(s)${res?.skipped ? `, skipped ${res.skipped}` : ""}.`);
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to clone lesson plans.")),
  });
}

// ── Library (Phase 6.5) ──────────────────────────────────────────────────────

export interface LibraryBookRow {
  id: string;
  title: string;
  author: string;
  isbn: string | null;
  category: string | null;
  publisher: string | null;
  publication_year: number | null;
  cover_url: string | null;
  shelf_location: string | null;
  total_copies: number;
  available_copies: number;
  description: string | null;
  created_at: string;
}

export interface LibraryLoanRow {
  id: string;
  book_id: string;
  book_title: string | null;
  book_author: string | null;
  book_category: string | null;
  borrower_user_id: string;
  borrower_name: string | null;
  borrower_email: string | null;
  borrowed_at: string;
  due_date: string;
  returned_at: string | null;
  status: "borrowed" | "returned";
  is_overdue: boolean;
  notes: string | null;
}

export function useLibraryBooks(params?: { search?: string; category?: string; available_only?: boolean; page?: number }) {
  return useQuery<{ items: LibraryBookRow[]; total: number; categories: string[] }>({
    queryKey: ["library", "books", params],
    queryFn: () => schoolApi.library.books.list(params),
    staleTime: 30_000,
  });
}

export function useCreateBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => schoolApi.library.books.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book added to the catalogue.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to add book.")),
  });
}

export function useUpdateBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => schoolApi.library.books.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book updated.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to update book.")),
  });
}

export function useDeleteBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.library.books.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book removed.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to remove book.")),
  });
}

export function useLibraryLoans(params?: { status?: "borrowed" | "returned" | "overdue"; borrower_user_id?: string; book_id?: string; page?: number; page_size?: number }) {
  return useQuery<{ items: LibraryLoanRow[]; total: number }>({
    queryKey: ["library", "loans", params],
    queryFn: () => schoolApi.library.loans.list(params),
    staleTime: 15_000,
  });
}

export function useMyLoans() {
  return useQuery<{ active: LibraryLoanRow[]; history: LibraryLoanRow[] }>({
    queryKey: ["library", "loans", "mine"],
    queryFn: () => schoolApi.library.loans.mine(),
    staleTime: 15_000,
  });
}

export function useIssueLoan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { book_id: string; borrower_user_id: string; due_date: string; notes?: string }) =>
      schoolApi.library.loans.issue(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book issued.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to issue book.")),
  });
}

export function useReturnLoan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => schoolApi.library.loans.returnLoan(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book returned.");
    },
    onError: (e) => toast.error(getApiErrorMessage(e, "Failed to return book.")),
  });
}

export function useLibraryStats() {
  return useQuery<{ total_books: number; total_copies: number; loans_out: number; overdue: number }>({
    queryKey: ["library", "stats"],
    queryFn: () => schoolApi.library.stats(),
    staleTime: 30_000,
  });
}

export function useTeacherAverageRating(teacher_id: string) {
  return useQuery({
    queryKey: ["teacher-avg-rating", teacher_id],
    queryFn: () => schoolApi.ratings.teacherAverage(teacher_id),
    enabled: !!teacher_id,
  });
}

// ── Grades / Report Cards ────────────────────────────────────────────────────

export function useSubmitGrades() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (grades: object[]) => schoolApi.grades.submit(grades),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["report-card"] });
      toast.success("Grades submitted successfully.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to submit grades."),
  });
}

export function useReportCard(student_id: string, term?: string) {
  return useQuery({
    queryKey: ["report-card", student_id, term],
    queryFn: () => schoolApi.grades.reportCard(student_id, term),
    enabled: !!student_id,
    staleTime: 60_000,
  });
}

// Author the human parts of a report (comments / attendance / next-term).
export function useSaveReportMeta() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ student_id, term, data }: { student_id: string; term: string; data: object }) =>
      schoolApi.grades.saveReportMeta(student_id, term, data),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: ["report-card", vars.student_id, vars.term] });
      toast.success("Report details saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save report details."),
  });
}

// R3 assessment-domain ratings (EYFS / skills / Cambridge) per student + term.
export function useDomainRatings(student_id: string, term: string) {
  return useQuery({
    queryKey: ["domain-ratings", student_id, term],
    queryFn: () => schoolApi.grades.domainRatings(student_id, term),
    enabled: !!student_id && !!term,
  });
}

export function useSaveDomainRatings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ student_id, data }: { student_id: string; data: { term: string; ratings: object[] } }) =>
      schoolApi.grades.saveDomainRatings(student_id, data),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: ["domain-ratings", vars.student_id, vars.data.term] });
      qc.invalidateQueries({ queryKey: ["report-card", vars.student_id, vars.data.term] });
      toast.success("Assessment ratings saved.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save ratings."),
  });
}
