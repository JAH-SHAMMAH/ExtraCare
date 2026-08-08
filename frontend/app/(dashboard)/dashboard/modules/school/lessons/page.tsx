"use client";

import { useMemo, useState, useRef } from "react";
import DOMPurify from "dompurify";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import {
  Plus, ChevronLeft, ChevronRight, Calendar, X, Loader2, CheckCircle2,
  Pencil, Trash2, BookOpen, Target, ListChecks, Wrench, FileText,
  ArrowRight, Bold, Italic, Underline, List, ListOrdered, Link as LinkIcon,
  AlignLeft, AlignCenter, AlignRight, Undo2, Redo2, Zap, Layers, Lightbulb,
  Sparkles, Link2, Users,
} from "lucide-react";
import {
  useLessonPlans, useCreateLessonPlan, useUpdateLessonPlan,
  usePublishLessonPlan, useDeleteLessonPlan, useLessonPlannerSettings,
  type LessonPlanRow,
} from "@/hooks/useSchool";
import { useMyContexts } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton } from "@/components/loading/Skeleton";
import { SuccessCriteriaTable } from "@/components/forms/SuccessCriteriaTable";
import { cn } from "@/lib/utils";

const DAYS = [
  { idx: 0, label: "Monday", short: "Mon" },
  { idx: 1, label: "Tuesday", short: "Tue" },
  { idx: 2, label: "Wednesday", short: "Wed" },
  { idx: 3, label: "Thursday", short: "Thu" },
  { idx: 4, label: "Friday", short: "Fri" },
];

/**
 * Lesson Planner — weekly view. The whole feature fits on one page:
 *   - Week navigation (← Prev | This week | Next →)
 *   - 5-column grid (Mon–Fri) with plans-per-day
 *   - Click a plan → right-side drawer with full detail + actions
 *   - "+ New" opens the drawer in create mode
 *
 * Demo priority: every cell shows something for the seeded week, and the
 * drawer works for both create and edit flows with the same component.
 */
export default function LessonPlannerPage() {
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeek(new Date()));
  const weekEnd = addDays(weekStart, 6);

  const [drawer, setDrawer] = useState<
    | { mode: "closed" }
    | { mode: "create"; prefillDate?: string }
    | { mode: "edit"; plan: LessonPlanRow }
  >({ mode: "closed" });

  const { data, isLoading } = useLessonPlans({
    mine: true,
    start_date: formatISO(weekStart),
    end_date: formatISO(weekEnd),
  });
  const showSkeleton = useDelayedFlag(isLoading);
  const plans = data?.items ?? [];

  const plansByDay = useMemo(() => {
    const grouped: Record<number, LessonPlanRow[]> = {};
    for (const p of plans) {
      const d = new Date(p.lesson_date);
      const dayIdx = (d.getDay() + 6) % 7; // Mon=0..Sun=6
      if (dayIdx > 4) continue;
      if (!grouped[dayIdx]) grouped[dayIdx] = [];
      grouped[dayIdx].push(p);
    }
    for (const k of Object.keys(grouped)) {
      grouped[Number(k)].sort(
        (a, b) => (a.period ?? 0) - (b.period ?? 0) || a.title.localeCompare(b.title),
      );
    }
    return grouped;
  }, [plans]);

  const todayIsInWeek = useMemo(() => {
    const today = new Date();
    return today >= weekStart && today <= weekEnd;
  }, [weekStart, weekEnd]);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Lesson Planner</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Lesson Planner</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Plan your week, class by class. Draft → publish when you&apos;re ready to share.
          </p>
        </div>
        <button
          onClick={() => setDrawer({ mode: "create" })}
          className="btn-primary gap-2"
        >
          <Plus size={15} />
          New Lesson Plan
        </button>
      </div>

      {/* Week navigation */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setWeekStart((d) => addDays(d, -7))}
            className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
            title="Previous week"
          >
            <ChevronLeft size={15} />
          </button>
          <button
            onClick={() => setWeekStart(startOfWeek(new Date()))}
            disabled={todayIsInWeek}
            className={cn(
              "px-3 h-8 rounded-lg text-xs font-semibold",
              todayIsInWeek
                ? "bg-brand-50 text-brand-700 cursor-default"
                : "text-slate-600 hover:bg-slate-100",
            )}
          >
            This week
          </button>
          <button
            onClick={() => setWeekStart((d) => addDays(d, 7))}
            className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
            title="Next week"
          >
            <ChevronRight size={15} />
          </button>
        </div>
        <div className="text-sm font-semibold text-slate-700">
          {formatNice(weekStart)} – {formatNice(addDays(weekStart, 4))}
        </div>
      </div>

      {/* Grid */}
      {showSkeleton ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {DAYS.map((d) => (
            <div key={d.idx} className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-20 w-full rounded-lg" />
              <Skeleton className="h-20 w-full rounded-lg" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {DAYS.map((d) => {
            const cellDate = addDays(weekStart, d.idx);
            const isToday = isSameDate(cellDate, new Date());
            const dayPlans = plansByDay[d.idx] ?? [];
            return (
              <DayColumn
                key={d.idx}
                label={d.label}
                short={d.short}
                date={cellDate}
                isToday={isToday}
                plans={dayPlans}
                onAdd={() => setDrawer({ mode: "create", prefillDate: formatISO(cellDate) })}
                onOpen={(p) => setDrawer({ mode: "edit", plan: p })}
              />
            );
          })}
        </div>
      )}

      {drawer.mode !== "closed" && (
        <PlanDrawer
          state={drawer}
          onClose={() => setDrawer({ mode: "closed" })}
        />
      )}
    </div>
  );
}

// ── Day column ───────────────────────────────────────────────────────────────

function DayColumn({
  label, short, date, isToday, plans, onAdd, onOpen,
}: {
  label: string;
  short: string;
  date: Date;
  isToday: boolean;
  plans: LessonPlanRow[];
  onAdd: () => void;
  onOpen: (p: LessonPlanRow) => void;
}) {
  return (
    <div className={cn(
      "bg-white rounded-xl border overflow-hidden flex flex-col",
      isToday ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200",
    )}>
      <div className={cn(
        "px-4 py-3 border-b flex items-center justify-between",
        isToday ? "bg-brand-50 border-brand-100" : "bg-slate-50/50 border-slate-100",
      )}>
        <div>
          <p className={cn(
            "text-xs font-black uppercase tracking-widest",
            isToday ? "text-brand-700" : "text-slate-500",
          )}>
            {short}
          </p>
          <p className={cn("text-[10px]", isToday ? "text-brand-600" : "text-slate-400")}>
            {label} · {date.getDate()} {date.toLocaleString("en-GB", { month: "short" })}
          </p>
        </div>
        {isToday && <span className="text-[10px] font-bold uppercase tracking-wider text-brand-600">Today</span>}
      </div>
      <div className="p-2 space-y-2 min-h-[280px] flex-1">
        {plans.length === 0 ? (
          <button
            onClick={onAdd}
            className="w-full h-full min-h-[240px] flex flex-col items-center justify-center text-center rounded-lg border-2 border-dashed border-slate-200 hover:border-brand-300 hover:bg-brand-50/30 transition-colors text-slate-400 hover:text-brand-600"
          >
            <Plus size={16} />
            <span className="text-[11px] font-semibold mt-1">Add plan</span>
          </button>
        ) : (
          <>
            {plans.map((p) => (
              <button
                key={p.id}
                onClick={() => onOpen(p)}
                className="w-full text-left rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-brand-50 hover:border-brand-200 p-3 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <span className={cn(
                    "badge text-[9px]",
                    p.status === "published"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-amber-50 text-amber-700 border-amber-200",
                  )}>
                    {p.status === "published" ? "Published" : "Draft"}
                  </span>
                  {p.period && (
                    <span className="text-[10px] font-bold text-slate-400">P{p.period}</span>
                  )}
                </div>
                <p className="text-sm font-bold text-slate-900 line-clamp-2 group-hover:text-brand-700">
                  {p.title}
                </p>
                <p className="text-[10px] text-slate-500 mt-1">
                  {[p.subject_name, p.class_name].filter(Boolean).join(" · ") || "—"}
                </p>
              </button>
            ))}
            <button
              onClick={onAdd}
              className="w-full mt-1 text-[10px] font-semibold text-slate-400 hover:text-brand-600 py-2 rounded-lg hover:bg-brand-50/30 transition-colors"
            >
              + Add another plan
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Drawer (create + edit) ───────────────────────────────────────────────────

type DrawerState =
  | { mode: "closed" }
  | { mode: "create"; prefillDate?: string }
  | { mode: "edit"; plan: LessonPlanRow };

function PlanDrawer({
  state, onClose,
}: {
  state: Exclude<DrawerState, { mode: "closed" }>;
  onClose: () => void;
}) {
  const isEdit = state.mode === "edit";
  const existing = isEdit ? state.plan : null;
  // Default a new plan's duration from the school's Lesson Planner Setup setting.
  const { data: plannerSettings } = useLessonPlannerSettings();

  const [form, setForm] = useState(() => ({
    // Core fields
    title: existing?.title ?? "",
    class_id: existing?.class_id ?? "",
    subject_id: existing?.subject_id ?? "",
    lesson_date: existing?.lesson_date
      ?? ("prefillDate" in state ? state.prefillDate : undefined)
      ?? formatISO(new Date()),
    period: existing?.period ?? 1,
    duration_minutes: existing?.duration_minutes ?? plannerSettings?.default_duration_minutes ?? 45,
    // Pedagogical rich-text fields
    theme: existing?.theme ?? "",
    sub_topic: existing?.sub_topic ?? "",
    the_hook: existing?.the_hook ?? "",
    prerequisite_knowledge: existing?.prerequisite_knowledge ?? "",
    rationale: existing?.rationale ?? "",
    methodologies: existing?.methodologies ?? "",
    reference: existing?.reference ?? "",
    // Metadata fields
    contact: existing?.contact ?? "",
    sex_demographics: existing?.sex_demographics ?? "All",
    average_age: existing?.average_age ?? "",
    no_in_class: existing?.no_in_class ?? "",
    // Content fields
    objectives: existing?.objectives ?? "",
    activities: existing?.activities ?? "",
    materials: existing?.materials ?? "",
    homework: existing?.homework ?? "",
    notes: existing?.notes ?? "",
    // Success criteria (JSON string)
    success_criteria: existing?.success_criteria ?? "",
  }));

  // Pull the teacher's own classes + subjects from /me/contexts. Intentional
  // scoping — teachers only plan for what they teach, and this avoids a
  // dependency on a global /school/classes endpoint.
  const { data: contexts } = useMyContexts();
  const classes = contexts?.as_teacher?.classes ?? [];
  const subjects = contexts?.as_teacher?.subjects ?? [];

  const createMut = useCreateLessonPlan();
  const updateMut = useUpdateLessonPlan();
  const publishMut = usePublishLessonPlan();
  const deleteMut = useDeleteLessonPlan();

  const busy = createMut.isPending || updateMut.isPending || publishMut.isPending || deleteMut.isPending;

  const save = async (publish = false) => {
    const payload = {
      ...form,
      status: publish ? "published" : (existing?.status ?? "draft"),
    };
    if (isEdit && existing) {
      await updateMut.mutateAsync({ id: existing.id, data: payload });
    } else {
      await createMut.mutateAsync(payload);
    }
    onClose();
  };

  const togglePublish = async () => {
    if (!existing) return;
    await publishMut.mutateAsync(existing.id);
    onClose();
  };

  const remove = async () => {
    if (!existing) return;
    if (!confirm("Remove this lesson plan? This can't be undone.")) return;
    await deleteMut.mutateAsync(existing.id);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Scrim */}
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />

      {/* Drawer */}
      <div className="relative ml-auto w-full max-w-2xl bg-white shadow-2xl overflow-y-auto animate-slide-in">
        <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {isEdit ? "Edit lesson plan" : "New lesson plan"}
            </p>
            <h2 className="text-lg font-black text-slate-900">
              {form.title || (isEdit ? existing!.title : "Untitled lesson")}
            </h2>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <div>
            <label className="label">Title *</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g. Quadratic equations — worked examples"
              className="input"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Class *</label>
              <select
                value={form.class_id}
                onChange={(e) => setForm({ ...form, class_id: e.target.value })}
                className="input"
              >
                <option value="">Select a class…</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Subject *</label>
              <select
                value={form.subject_id}
                onChange={(e) => setForm({ ...form, subject_id: e.target.value })}
                className="input"
              >
                <option value="">Select a subject…</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.code ? ` (${s.code})` : ""}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Metadata fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Contact</label>
              <input
                type="text"
                value={form.contact}
                onChange={(e) => setForm({ ...form, contact: e.target.value })}
                placeholder="Name or role of lesson deliverer"
                className="input"
              />
            </div>
            <div>
              <label className="label">Demographics</label>
              <select
                value={form.sex_demographics}
                onChange={(e) => setForm({ ...form, sex_demographics: e.target.value })}
                className="input"
              >
                <option value="All">All</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>
            <div>
              <label className="label">Average Age</label>
              <input
                type="number"
                min={3}
                max={25}
                value={form.average_age || ""}
                onChange={(e) => setForm({ ...form, average_age: e.target.value ? Number(e.target.value) : "" })}
                placeholder="e.g., 12"
                className="input"
              />
            </div>
            <div>
              <label className="label">No. in Class</label>
              <input
                type="number"
                min={1}
                max={999}
                value={form.no_in_class || ""}
                onChange={(e) => setForm({ ...form, no_in_class: e.target.value ? Number(e.target.value) : "" })}
                placeholder="e.g., 35"
                className="input"
              />
            </div>
          </div>

          {/* Scheduling fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Date *</label>
              <input
                type="date"
                value={form.lesson_date}
                onChange={(e) => setForm({ ...form, lesson_date: e.target.value })}
                className="input"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Period</label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={form.period ?? ""}
                  onChange={(e) => setForm({ ...form, period: e.target.value ? Number(e.target.value) : 1 })}
                  className="input"
                />
              </div>
              <div>
                <label className="label">Duration (min)</label>
                <input
                  type="number"
                  min={15}
                  max={240}
                  step={5}
                  value={form.duration_minutes ?? 45}
                  onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) || 45 })}
                  className="input"
                />
              </div>
            </div>
          </div>

          {/* Planning fields (pedagogical structure) */}
          <RichTextField
            icon={Layers}
            label="Theme"
            placeholder="The broader unit or topic this lesson belongs to"
            value={form.theme}
            onChange={(v) => setForm({ ...form, theme: v })}
          />
          <RichTextField
            icon={Target}
            label="Sub-Topic"
            placeholder="The specific sub-topic covered in this lesson"
            value={form.sub_topic}
            onChange={(v) => setForm({ ...form, sub_topic: v })}
          />
          <RichTextField
            icon={Zap}
            label="The Hook"
            placeholder="How you'll open and engage students (5–10 min opener)"
            value={form.the_hook}
            onChange={(v) => setForm({ ...form, the_hook: v })}
          />

          <RichTextField
            icon={Target}
            label="Objectives"
            placeholder="What will students know or be able to do by the end?"
            value={form.objectives}
            onChange={(v) => setForm({ ...form, objectives: v })}
          />
          <RichTextField
            icon={ListChecks}
            label="Activities"
            placeholder="Step-by-step flow of the lesson."
            value={form.activities}
            onChange={(v) => setForm({ ...form, activities: v })}
          />

          {/* Pedagogical foundations */}
          <RichTextField
            icon={BookOpen}
            label="Pre-Requisite Knowledge"
            placeholder="What students must know before starting this lesson"
            value={form.prerequisite_knowledge}
            onChange={(v) => setForm({ ...form, prerequisite_knowledge: v })}
          />
          <RichTextField
            icon={Lightbulb}
            label="Rationale"
            placeholder="Why use this teaching approach?"
            value={form.rationale}
            onChange={(v) => setForm({ ...form, rationale: v })}
          />
          <RichTextField
            icon={Sparkles}
            label="21st Century Methodologies"
            placeholder="Which modern teaching methods (collaborative learning, critical thinking, etc.)"
            value={form.methodologies}
            onChange={(v) => setForm({ ...form, methodologies: v })}
          />

          <RichTextField
            icon={Wrench}
            label="Materials"
            placeholder="Books, handouts, equipment, slides…"
            value={form.materials}
            onChange={(v) => setForm({ ...form, materials: v })}
          />
          <RichTextField
            icon={Link2}
            label="Reference"
            placeholder="Source materials, textbooks, page numbers, URLs"
            value={form.reference}
            onChange={(v) => setForm({ ...form, reference: v })}
          />

          {/* Success criteria matrix */}
          <SuccessCriteriaTable
            value={form.success_criteria}
            onChange={(v) => setForm({ ...form, success_criteria: v })}
          />
          <RichTextField
            icon={BookOpen}
            label="Homework"
            placeholder="What students take home."
            value={form.homework}
            onChange={(v) => setForm({ ...form, homework: v })}
          />
          <RichTextField
            icon={FileText}
            label="Private notes"
            placeholder="Just for you — won't be shared with students or parents."
            value={form.notes}
            onChange={(v) => setForm({ ...form, notes: v })}
          />
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            {isEdit && (
              <button
                onClick={remove}
                disabled={busy}
                className="text-sm font-semibold text-rose-600 hover:text-rose-700 flex items-center gap-1.5"
              >
                <Trash2 size={14} /> Delete
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} disabled={busy} className="btn-secondary">Cancel</button>
            {isEdit && existing?.status === "draft" ? (
              <>
                <button onClick={() => save(false)} disabled={busy} className="btn-secondary gap-2">
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <Pencil size={14} />}
                  Save draft
                </button>
                <button onClick={togglePublish} disabled={busy} className="btn-primary gap-2">
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Publish
                </button>
              </>
            ) : isEdit ? (
              <button onClick={() => save(false)} disabled={busy} className="btn-primary gap-2">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Pencil size={14} />}
                Save changes
              </button>
            ) : (
              <>
                <button onClick={() => save(false)} disabled={busy} className="btn-secondary">
                  {createMut.isPending && !publishMut.isPending ? <Loader2 size={14} className="animate-spin" /> : null}
                  Save as draft
                </button>
                <button onClick={() => save(true)} disabled={busy} className="btn-primary gap-2">
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Save & publish
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Sanitization config (defense in depth)
const SANITIZE_CONFIG = {
  ALLOWED_TAGS: ["p", "br", "strong", "em", "u", "ol", "ul", "li", "a", "table", "tr", "td", "th", "thead", "tbody"],
  ALLOWED_ATTR: ["href", "target"],
  KEEP_CONTENT: true,
};

function sanitizeHTML(html: string): string {
  return DOMPurify.sanitize(html, SANITIZE_CONFIG);
}

// Detect if content is plain text (no HTML tags) for backwards compatibility
function isPlainText(content: string): boolean {
  return !/<[^>]+>/.test(content);
}

// Convert plain text newlines to <br> for HTML rendering
function plainTextToHTML(text: string): string {
  return text.split("\n").map(line => `<p>${DOMPurify.sanitize(line)}</p>`).join("");
}

function RichTextField({
  icon: Icon, label, placeholder, value, onChange,
}: {
  icon: typeof Target;
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
    ],
    content: value,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const sanitized = sanitizeHTML(html);
      onChange(sanitized);
    },
  });

  if (!editor) return null;

  return (
    <div>
      <label className="label flex items-center gap-1.5">
        <Icon size={13} className="text-slate-400" /> {label}
      </label>

      {/* Toolbar */}
      <div className="border border-b-0 border-slate-200 rounded-t-lg bg-slate-50 p-2 flex flex-wrap gap-1">
        <button
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive("bold") && "bg-slate-200")}
          title="Bold"
        >
          <Bold size={14} />
        </button>
        <button
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive("italic") && "bg-slate-200")}
          title="Italic"
        >
          <Italic size={14} />
        </button>
        <button
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive("underline") && "bg-slate-200")}
          title="Underline"
        >
          <Underline size={14} />
        </button>

        <div className="w-px bg-slate-300 mx-1" />

        <button
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive({ textAlign: "left" }) && "bg-slate-200")}
          title="Align left"
        >
          <AlignLeft size={14} />
        </button>
        <button
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive({ textAlign: "center" }) && "bg-slate-200")}
          title="Align center"
        >
          <AlignCenter size={14} />
        </button>
        <button
          onClick={() => editor.chain().focus().setTextAlign("right").run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive({ textAlign: "right" }) && "bg-slate-200")}
          title="Align right"
        >
          <AlignRight size={14} />
        </button>

        <div className="w-px bg-slate-300 mx-1" />

        <button
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive("bulletList") && "bg-slate-200")}
          title="Bullet list"
        >
          <List size={14} />
        </button>
        <button
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive("orderedList") && "bg-slate-200")}
          title="Numbered list"
        >
          <ListOrdered size={14} />
        </button>

        <div className="w-px bg-slate-300 mx-1" />

        <button
          onClick={() => {
            const url = window.prompt("Enter URL:");
            if (url) editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
          }}
          className={cn("p-2 rounded hover:bg-slate-200 transition", editor.isActive("link") && "bg-slate-200")}
          title="Link"
        >
          <LinkIcon size={14} />
        </button>

        <div className="w-px bg-slate-300 mx-1" />

        <button
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          className="p-2 rounded hover:bg-slate-200 disabled:opacity-50 transition"
          title="Undo"
        >
          <Undo2 size={14} />
        </button>
        <button
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          className="p-2 rounded hover:bg-slate-200 disabled:opacity-50 transition"
          title="Redo"
        >
          <Redo2 size={14} />
        </button>
      </div>

      {/* Editor */}
      <div className="border border-slate-200 rounded-b-lg overflow-hidden prose prose-sm max-w-none">
        <EditorContent
          editor={editor}
          className="p-3 min-h-[84px] bg-white text-slate-700 focus:outline-none"
        />
      </div>
    </div>
  );
}

// ── Date helpers ─────────────────────────────────────────────────────────────

function startOfWeek(d: Date): Date {
  const copy = new Date(d);
  const day = (copy.getDay() + 6) % 7; // Mon=0..Sun=6
  copy.setDate(copy.getDate() - day);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

function formatISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatNice(d: Date): string {
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function isSameDate(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
