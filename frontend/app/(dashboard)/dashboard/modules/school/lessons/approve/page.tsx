"use client";

import { useMemo, useState } from "react";
import {
  useLessonPlans, usePublishLessonPlan, useUpdateLessonPlan,
  useClasses, useSubjects, useTeachers,
  type LessonPlanRow,
} from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import {
  ClipboardCheck, Loader2, CheckCircle2, Undo2, Eye, X, Filter,
  Target, ListChecks, Wrench, BookOpen, FileText,
} from "lucide-react";

/**
 * Approve Lesson Plans — supervisor queue over the shared lesson-plan lifecycle.
 * Our model has no separate "approved" state; a published plan IS the approved,
 * shareable one. So here publish = Approve and return-to-draft = send back for
 * revision. The backend scopes non-admins to their own plans, so this reads as a
 * cross-teacher review desk for supervisors and a "my plans" view for a teacher.
 */
export default function ApproveLessonPlansPage() {
  const canWrite = useHasPermission("school:lessons:write");
  const [statusFilter, setStatusFilter] = useState<"draft" | "published" | "">("draft");
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [viewing, setViewing] = useState<LessonPlanRow | null>(null);

  const { data: classesResp } = useClasses({ page_size: 100 });
  const { data: subjectsResp } = useSubjects({ page_size: 100 });
  const { data: teachersResp } = useTeachers({ page_size: 100 });
  const classes = classesResp?.items ?? [];
  const subjects = subjectsResp?.items ?? [];
  const teachers = teachersResp?.items ?? [];

  const { data, isLoading } = useLessonPlans({
    status: statusFilter || undefined,
    class_id: classId || undefined,
    subject_id: subjectId || undefined,
    teacher_id: teacherId || undefined,
    start_date: from || undefined,
    end_date: to || undefined,
  });
  const plans = data?.items ?? [];

  const publish = usePublishLessonPlan();
  const update = useUpdateLessonPlan();
  const busyId = publish.isPending || update.isPending;

  const pendingCount = useMemo(() => plans.filter((p) => p.status === "draft").length, [plans]);

  const approve = (p: LessonPlanRow) => publish.mutate(p.id);
  const returnToDraft = (p: LessonPlanRow) => update.mutate({ id: p.id, data: { status: "draft" } });

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span><span>/</span><span>Lesson Planner</span><span>/</span>
          <span className="text-brand-600 font-semibold">Approve Lesson Plans</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          <ClipboardCheck size={22} className="text-brand-600" /> Approve Lesson Plans
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Review teachers&apos; plans and approve them to publish. {statusFilter === "draft" && pendingCount > 0 && (
            <span className="font-semibold text-amber-600">{pendingCount} awaiting approval.</span>
          )}
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">
          <Filter size={13} /> Filters
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div>
            <label className="label">Status</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)} className="input">
              <option value="draft">Pending</option>
              <option value="published">Approved</option>
              <option value="">All</option>
            </select>
          </div>
          <div>
            <label className="label">Class</label>
            <select value={classId} onChange={(e) => setClassId(e.target.value)} className="input">
              <option value="">All classes</option>
              {classes.map((c: any) => (<option key={c.id} value={c.id}>{c.name}</option>))}
            </select>
          </div>
          <div>
            <label className="label">Subject</label>
            <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input">
              <option value="">All subjects</option>
              {subjects.map((s: any) => (<option key={s.id} value={s.id}>{s.name}</option>))}
            </select>
          </div>
          <div>
            <label className="label">Teacher</label>
            <select value={teacherId} onChange={(e) => setTeacherId(e.target.value)} className="input">
              <option value="">All teachers</option>
              {teachers.map((t: any) => (<option key={t.id} value={t.id}>{[t.first_name, t.last_name].filter(Boolean).join(" ") || t.email}</option>))}
            </select>
          </div>
          <div>
            <label className="label">From</label>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="input" />
          </div>
          <div>
            <label className="label">To</label>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="input" />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["Teacher", "Class", "Subject", "Date", "Title", "Status", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}><td colSpan={7} className="px-4 py-3"><div className="h-4 bg-slate-100 rounded animate-pulse w-full" /></td></tr>
                ))
              ) : plans.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400 text-sm">
                  <ClipboardCheck size={28} className="mx-auto mb-2 opacity-40" />
                  No lesson plans match these filters.
                </td></tr>
              ) : plans.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50/50">
                  <td className="px-4 py-3 text-sm text-slate-700 whitespace-nowrap">{p.teacher_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600 whitespace-nowrap">{p.class_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600 whitespace-nowrap">{p.subject_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600 tabular-nums whitespace-nowrap">{fmtDate(p.lesson_date)}{p.period ? ` · P${p.period}` : ""}</td>
                  <td className="px-4 py-3 text-sm font-medium text-slate-900 max-w-[240px] truncate">{p.title}</td>
                  <td className="px-4 py-3">
                    <span className={cn("badge text-[10px]", p.status === "published"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-amber-50 text-amber-700 border-amber-200")}>
                      {p.status === "published" ? "Approved" : "Pending"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => setViewing(p)} className="btn-secondary text-xs py-1 gap-1"><Eye size={12} /> View</button>
                      {canWrite && (p.status === "draft" ? (
                        <button onClick={() => approve(p)} disabled={busyId} className="btn-primary text-xs py-1 gap-1">
                          {publish.isPending ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />} Approve
                        </button>
                      ) : (
                        <button onClick={() => returnToDraft(p)} disabled={busyId} className="btn-secondary text-xs py-1 gap-1">
                          <Undo2 size={12} /> Return
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {viewing && <PlanViewModal plan={viewing} canWrite={canWrite} busy={busyId}
        onApprove={() => { approve(viewing); setViewing(null); }}
        onReturn={() => { returnToDraft(viewing); setViewing(null); }}
        onClose={() => setViewing(null)} />}
    </div>
  );
}

function PlanViewModal({ plan, canWrite, busy, onApprove, onReturn, onClose }: {
  plan: LessonPlanRow; canWrite: boolean; busy: boolean;
  onApprove: () => void; onReturn: () => void; onClose: () => void;
}) {
  const sections = [
    { icon: Target, label: "Objectives", value: plan.objectives },
    { icon: ListChecks, label: "Activities", value: plan.activities },
    { icon: Wrench, label: "Materials", value: plan.materials },
    { icon: BookOpen, label: "Homework", value: plan.homework },
    { icon: FileText, label: "Teacher notes", value: plan.notes },
  ];
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-xl bg-white shadow-2xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Lesson plan</p>
            <h2 className="text-lg font-black text-slate-900">{plan.title}</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {[plan.teacher_name, plan.class_name, plan.subject_name].filter(Boolean).join(" · ")} · {fmtDate(plan.lesson_date)}
            </p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <span className={cn("badge text-[10px]", plan.status === "published"
            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
            : "bg-amber-50 text-amber-700 border-amber-200")}>
            {plan.status === "published" ? "Approved" : "Pending approval"}
          </span>
          {sections.map((s) => (
            <div key={s.label}>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5 mb-1"><s.icon size={12} /> {s.label}</p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{s.value || <span className="text-slate-300">—</span>}</p>
            </div>
          ))}
        </div>
        {canWrite && (
          <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex justify-end gap-2">
            {plan.status === "draft" ? (
              <button onClick={onApprove} disabled={busy} className="btn-primary gap-2">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />} Approve &amp; publish
              </button>
            ) : (
              <button onClick={onReturn} disabled={busy} className="btn-secondary gap-2"><Undo2 size={14} /> Return to draft</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
