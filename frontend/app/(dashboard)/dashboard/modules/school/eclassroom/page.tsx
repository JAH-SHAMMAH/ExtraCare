"use client";

import { useState } from "react";
import {
  useAssignments,
  useCreateAssignment,
  useUpdateAssignment,
  useDeleteAssignment,
  useAssignmentSubmissions,
  useGradeSubmission,
} from "@/hooks/useSchoolExperience";
import { useMineFilter } from "@/hooks/useMineFilter";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  BookOpen, Plus, X, Loader2, Edit2, Trash2, ClipboardList,
  Calendar, CheckCircle2, Clock, MoreVertical, ArrowLeft, Award,
} from "lucide-react";
import type { Assignment, AssignmentStatus, AssignmentSubmission } from "@/types";

const STATUS_STYLES: Record<AssignmentStatus, string> = {
  draft: "bg-slate-50 text-slate-600 border-slate-200",
  published: "bg-emerald-50 text-emerald-700 border-emerald-200",
  closed: "bg-amber-50 text-amber-700 border-amber-200",
};

export default function EClassroomPage() {
  const canWrite = useHasPermission("school:write");
  const { mine, setMine } = useMineFilter();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Assignment | null>(null);
  const [openSubsFor, setOpenSubsFor] = useState<Assignment | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const { data, isLoading } = useAssignments({
    status: statusFilter || undefined,
    for_me: mine || undefined,
    page: 1,
    page_size: 50,
  });
  const createAssignment = useCreateAssignment();
  const updateAssignment = useUpdateAssignment();
  const deleteAssignment = useDeleteAssignment();

  const [form, setForm] = useState({
    title: "",
    description: "",
    instructions: "",
    class_id: "",
    subject_id: "",
    teacher_id: "",
    due_date: "",
    max_points: 100,
    status: "draft" as AssignmentStatus,
  });

  const resetForm = () => {
    setForm({
      title: "", description: "", instructions: "", class_id: "", subject_id: "",
      teacher_id: "", due_date: "", max_points: 100, status: "draft",
    });
    setEditing(null);
    setShowForm(false);
  };

  const handleSubmit = () => {
    const payload = {
      ...form,
      due_date: form.due_date || null,
      subject_id: form.subject_id || null,
      description: form.description || null,
      instructions: form.instructions || null,
    };
    if (editing) {
      updateAssignment.mutate({ id: editing.id, data: payload }, { onSuccess: resetForm });
    } else {
      createAssignment.mutate(payload, { onSuccess: resetForm });
    }
  };

  const handleEdit = (a: Assignment) => {
    setForm({
      title: a.title,
      description: a.description || "",
      instructions: a.instructions || "",
      class_id: a.class_id,
      subject_id: a.subject_id || "",
      teacher_id: a.teacher_id,
      due_date: a.due_date ? a.due_date.substring(0, 16) : "",
      max_points: a.max_points,
      status: a.status,
    });
    setEditing(a);
    setShowForm(true);
    setMenuOpen(null);
  };

  const handleDelete = (id: string) => {
    if (confirm("Delete this assignment? Submissions will be preserved.")) {
      deleteAssignment.mutate(id);
    }
    setMenuOpen(null);
  };

  if (openSubsFor) {
    return <SubmissionsView assignment={openSubsFor} onBack={() => setOpenSubsFor(null)} canGrade={canWrite} />;
  }

  const items = data?.items as Assignment[] | undefined;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Classwork</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Classwork</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Publish assignments, collect submissions, grade student work.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2">
            <Plus size={15} />
            New Assignment
          </button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Assignments", value: data?.total ?? "—" },
          { label: "Published", value: items?.filter((a) => a.status === "published").length ?? "—" },
          { label: "Drafts", value: items?.filter((a) => a.status === "draft").length ?? "—" },
          { label: "Closed", value: items?.filter((a) => a.status === "closed").length ?? "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">
              {editing ? "Edit Assignment" : "New Assignment"}
            </h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Title *</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" placeholder="Chapter 3 – Algebra Practice" />
            </div>
            <div>
              <label className="label">Class ID *</label>
              <input value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Subject ID</label>
              <input value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Teacher ID *</label>
              <input value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Due Date</label>
              <input type="datetime-local" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Max Points</label>
              <input type="number" value={form.max_points} onChange={(e) => setForm({ ...form, max_points: Number(e.target.value) })} className="input" />
            </div>
            <div>
              <label className="label">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as AssignmentStatus })} className="input">
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={2} />
            </div>
            <div className="md:col-span-2">
              <label className="label">Instructions</label>
              <textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} className="input" rows={4} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button
              onClick={handleSubmit}
              disabled={createAssignment.isPending || updateAssignment.isPending}
              className="btn-primary gap-2"
            >
              {(createAssignment.isPending || updateAssignment.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Publish"}
            </button>
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex items-center gap-3">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-48">
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="closed">Closed</option>
        </select>
        {mine && (
          <button
            onClick={() => setMine(false)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-700 bg-brand-50 border border-brand-200 rounded-lg px-3 py-1.5 hover:bg-brand-100"
          >
            Showing: Mine
            <X size={12} />
          </button>
        )}
      </div>

      {/* Assignment grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items && items.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((a) => (
            <div key={a.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
                  <BookOpen size={18} className="text-indigo-600" />
                </div>
                <div className="flex items-center gap-1">
                  <span className={cn("badge border", STATUS_STYLES[a.status])}>{a.status}</span>
                  {canWrite && (
                    <div className="relative">
                      <button onClick={() => setMenuOpen(menuOpen === a.id ? null : a.id)} className="p-1 rounded hover:bg-slate-100">
                        <MoreVertical size={14} className="text-slate-400" />
                      </button>
                      {menuOpen === a.id && (
                        <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                          <button onClick={() => handleEdit(a)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                            <Edit2 size={13} /> Edit
                          </button>
                          <button onClick={() => handleDelete(a.id)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                            <Trash2 size={13} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-1 line-clamp-2">{a.title}</h3>
              {a.description && <p className="text-xs text-slate-500 mb-3 line-clamp-2">{a.description}</p>}
              <div className="space-y-1 mb-3">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Calendar size={12} />
                  Due {a.due_date ? formatDate(a.due_date) : "—"}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Award size={12} />
                  {a.max_points} points
                </div>
              </div>
              <button
                onClick={() => setOpenSubsFor(a)}
                className="w-full text-xs font-semibold text-brand-600 hover:text-brand-700 border-t border-slate-100 pt-3 flex items-center justify-center gap-1"
              >
                <ClipboardList size={13} />
                View Submissions
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-20 text-slate-400">
          <BookOpen size={40} className="mb-3 opacity-40" />
          <p className="font-semibold">No assignments yet</p>
          <p className="text-sm mt-1">Create your first assignment to get started.</p>
        </div>
      )}
    </div>
  );
}

function SubmissionsView({
  assignment,
  onBack,
  canGrade,
}: {
  assignment: Assignment;
  onBack: () => void;
  canGrade: boolean;
}) {
  const { data, isLoading } = useAssignmentSubmissions(assignment.id);
  const gradeSubmission = useGradeSubmission();
  const [grading, setGrading] = useState<string | null>(null);
  const [score, setScore] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");

  const startGrade = (s: AssignmentSubmission) => {
    setGrading(s.id);
    setScore(s.score?.toString() || "");
    setFeedback(s.feedback || "");
  };

  const saveGrade = (id: string) => {
    const numScore = Number(score);
    if (Number.isNaN(numScore)) return;
    gradeSubmission.mutate(
      { id, score: numScore, feedback: feedback || undefined },
      { onSuccess: () => { setGrading(null); setScore(""); setFeedback(""); } },
    );
  };

  const submissions = data as AssignmentSubmission[] | undefined;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft size={14} /> Back to assignments
      </button>
      <div className="mb-6">
        <h1 className="text-2xl font-black text-slate-900">{assignment.title}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {submissions?.length ?? 0} submissions · Max {assignment.max_points} points
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : submissions && submissions.length > 0 ? (
        <div className="space-y-3">
          {submissions.map((s) => (
            <div key={s.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-bold text-slate-900">Student {s.student_id.slice(0, 8)}</p>
                  <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                    <Clock size={11} />
                    Submitted {s.submitted_at ? formatDate(s.submitted_at) : "—"}
                  </p>
                </div>
                <span className={cn(
                  "badge border",
                  s.status === "graded" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200",
                )}>
                  {s.status === "graded" && <CheckCircle2 size={10} className="mr-1" />}
                  {s.status}
                </span>
              </div>
              {s.content && <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3 mb-3 whitespace-pre-wrap">{s.content}</p>}
              {s.file_url && (
                <a href={s.file_url} target="_blank" rel="noreferrer" className="text-xs text-brand-600 hover:underline">
                  View attachment →
                </a>
              )}

              {grading === s.id ? (
                <div className="mt-4 bg-slate-50 rounded-lg p-4 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label">Score (max {assignment.max_points})</label>
                      <input
                        type="number"
                        value={score}
                        onChange={(e) => setScore(e.target.value)}
                        className="input"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="label">Feedback</label>
                    <textarea value={feedback} onChange={(e) => setFeedback(e.target.value)} className="input" rows={3} />
                  </div>
                  <div className="flex justify-end gap-2">
                    <button onClick={() => setGrading(null)} className="btn-secondary">Cancel</button>
                    <button onClick={() => saveGrade(s.id)} disabled={gradeSubmission.isPending} className="btn-primary gap-2">
                      {gradeSubmission.isPending && <Loader2 size={14} className="animate-spin" />}
                      Save Grade
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3">
                  <div className="text-sm">
                    {s.score != null ? (
                      <>
                        <span className="font-bold text-slate-900">{s.score}</span>
                        <span className="text-slate-400"> / {assignment.max_points}</span>
                      </>
                    ) : (
                      <span className="text-slate-400 text-xs">Not graded</span>
                    )}
                  </div>
                  {canGrade && (
                    <button onClick={() => startGrade(s)} className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                      {s.score != null ? "Update grade" : "Grade"}
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <ClipboardList size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No submissions yet</p>
        </div>
      )}
    </div>
  );
}
