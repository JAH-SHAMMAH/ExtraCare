"use client";

import { useState } from "react";
import {
  useCBTExams,
  useCBTExam,
  useCreateCBTExam,
  useUpdateCBTExam,
  useDeleteCBTExam,
  useCBTQuestions,
  useAddCBTQuestion,
  useDeleteCBTQuestion,
  useAddFromBank,
  useBankItems,
  useCBTSettings,
} from "@/hooks/useSchoolExperience";
import { useMineFilter } from "@/hooks/useMineFilter";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  MonitorCheck, Plus, X, Loader2, Edit2, Trash2, ArrowLeft,
  ListChecks, Clock, Award, FileQuestion, MoreVertical, Search,
} from "lucide-react";
import type { CBTExam, CBTExamStatus, CBTQuestion, CBTQuestionType } from "@/types";

const EXAM_STATUS_STYLES: Record<CBTExamStatus, string> = {
  draft: "bg-slate-50 text-slate-600 border-slate-200",
  published: "bg-sky-50 text-sky-700 border-sky-200",
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  closed: "bg-amber-50 text-amber-700 border-amber-200",
};

export default function CBTPage() {
  const canWrite = useHasPermission("school:write");
  const { mine, setMine } = useMineFilter();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<CBTExam | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [openExamId, setOpenExamId] = useState<string | null>(null);

  const { data, isLoading } = useCBTExams({
    status: statusFilter || undefined,
    for_me: mine || undefined,
    page: 1,
    page_size: 50,
  });
  const createExam = useCreateCBTExam();
  const updateExam = useUpdateCBTExam();
  const deleteExam = useDeleteCBTExam();
  const { data: cbtSettings } = useCBTSettings();

  const [form, setForm] = useState({
    title: "",
    description: "",
    class_id: "",
    subject_id: "",
    start_time: "",
    end_time: "",
    duration_minutes: 60,
    shuffle_questions: false,
    max_attempts: 1,
    status: "draft" as CBTExamStatus,
  });

  const resetForm = () => {
    setForm({
      title: "", description: "", class_id: "", subject_id: "",
      start_time: "", end_time: "",
      duration_minutes: cbtSettings?.default_duration_minutes ?? 60,
      shuffle_questions: cbtSettings?.shuffle_default ?? false,
      max_attempts: 1,
      status: "draft",
    });
    setEditing(null);
    setShowForm(false);
  };

  const handleSubmit = () => {
    const payload = {
      ...form,
      description: form.description || null,
      class_id: form.class_id || null,
      subject_id: form.subject_id || null,
      start_time: form.start_time || null,
      end_time: form.end_time || null,
    };
    if (editing) {
      updateExam.mutate({ id: editing.id, data: payload }, { onSuccess: resetForm });
    } else {
      createExam.mutate(payload, { onSuccess: resetForm });
    }
  };

  const handleEdit = (e: CBTExam) => {
    setForm({
      title: e.title,
      description: e.description || "",
      class_id: e.class_id || "",
      subject_id: e.subject_id || "",
      start_time: e.start_time ? e.start_time.substring(0, 16) : "",
      end_time: e.end_time ? e.end_time.substring(0, 16) : "",
      duration_minutes: e.duration_minutes,
      shuffle_questions: e.shuffle_questions,
      max_attempts: e.max_attempts ?? 1,
      status: e.status,
    });
    setEditing(e);
    setShowForm(true);
    setMenuOpen(null);
  };

  const handleDelete = (id: string) => {
    if (confirm("Delete this exam? All questions and attempts will be lost.")) {
      deleteExam.mutate(id);
    }
    setMenuOpen(null);
  };

  if (openExamId) {
    return <ExamBuilder examId={openExamId} onBack={() => setOpenExamId(null)} canWrite={canWrite} />;
  }

  const exams = data?.items as CBTExam[] | undefined;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">CBT</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Computer-Based Tests</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Build online exams, auto-grade objective questions, and track attempts.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2">
            <Plus size={15} />
            New Exam
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Exams", value: data?.total ?? "—" },
          { label: "Active", value: exams?.filter((e) => e.status === "active").length ?? "—" },
          { label: "Published", value: exams?.filter((e) => e.status === "published").length ?? "—" },
          { label: "Drafts", value: exams?.filter((e) => e.status === "draft").length ?? "—" },
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
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Exam" : "New Exam"}</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Title *</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Class ID</label>
              <input value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Subject ID</label>
              <input value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Start Time</label>
              <input type="datetime-local" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">End Time</label>
              <input type="datetime-local" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Duration (minutes)</label>
              <input type="number" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })} className="input" />
            </div>
            <div>
              <label className="label">Max attempts</label>
              <input type="number" min="0" value={form.max_attempts} onChange={(e) => setForm({ ...form, max_attempts: Number(e.target.value) })} className="input" />
              <p className="text-[11px] text-slate-400 mt-1">1 = single sitting · 0 = unlimited</p>
            </div>
            <div>
              <label className="label">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as CBTExamStatus })} className="input">
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="active">Active</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            <div className="md:col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                id="shuffle"
                checked={form.shuffle_questions}
                onChange={(e) => setForm({ ...form, shuffle_questions: e.target.checked })}
              />
              <label htmlFor="shuffle" className="text-xs font-medium text-slate-700">Shuffle questions for each student</label>
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createExam.isPending || updateExam.isPending} className="btn-primary gap-2">
              {(createExam.isPending || updateExam.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex items-center gap-3">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-48">
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="active">Active</option>
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

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : exams && exams.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {exams.map((e) => (
            <div key={e.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-sky-50 border border-sky-100 flex items-center justify-center shrink-0">
                  <MonitorCheck size={18} className="text-sky-600" />
                </div>
                <div className="flex items-center gap-1">
                  <span className={cn("badge border", EXAM_STATUS_STYLES[e.status])}>{e.status}</span>
                  {canWrite && (
                    <div className="relative">
                      <button onClick={() => setMenuOpen(menuOpen === e.id ? null : e.id)} className="p-1 rounded hover:bg-slate-100">
                        <MoreVertical size={14} className="text-slate-400" />
                      </button>
                      {menuOpen === e.id && (
                        <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                          <button onClick={() => handleEdit(e)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                            <Edit2 size={13} /> Edit
                          </button>
                          <button onClick={() => handleDelete(e.id)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                            <Trash2 size={13} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-1 line-clamp-2">{e.title}</h3>
              {e.description && <p className="text-xs text-slate-500 mb-3 line-clamp-2">{e.description}</p>}
              <div className="space-y-1 mb-3">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Clock size={12} />
                  {e.duration_minutes} min duration
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Award size={12} />
                  {e.total_points} points total
                </div>
                {e.start_time && (
                  <div className="text-xs text-slate-400">Starts {formatDate(e.start_time)}</div>
                )}
              </div>
              <button
                onClick={() => setOpenExamId(e.id)}
                className="w-full text-xs font-semibold text-brand-600 hover:text-brand-700 border-t border-slate-100 pt-3 flex items-center justify-center gap-1"
              >
                <ListChecks size={13} />
                Manage Questions
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-20 text-slate-400">
          <MonitorCheck size={40} className="mb-3 opacity-40" />
          <p className="font-semibold">No exams yet</p>
          <p className="text-sm mt-1">Create your first CBT exam.</p>
        </div>
      )}
    </div>
  );
}

function ExamBuilder({ examId, onBack, canWrite }: { examId: string; onBack: () => void; canWrite: boolean }) {
  const { data: exam } = useCBTExam(examId);
  const { data: questions, isLoading } = useCBTQuestions(examId, canWrite);
  const addQuestion = useAddCBTQuestion();
  const deleteQuestion = useDeleteCBTQuestion();
  const [showForm, setShowForm] = useState(false);
  const [showBank, setShowBank] = useState(false);

  const [qform, setQform] = useState({
    question_text: "",
    question_type: "mcq" as CBTQuestionType,
    options: [
      { key: "A", text: "" },
      { key: "B", text: "" },
      { key: "C", text: "" },
      { key: "D", text: "" },
    ],
    correct_answer: "",
    points: 1,
    position: 0,
  });

  const resetQForm = () => {
    setQform({
      question_text: "",
      question_type: "mcq",
      options: [
        { key: "A", text: "" },
        { key: "B", text: "" },
        { key: "C", text: "" },
        { key: "D", text: "" },
      ],
      correct_answer: "",
      points: 1,
      position: 0,
    });
    setShowForm(false);
  };

  const handleAdd = () => {
    const list = (questions as CBTQuestion[]) || [];
    const payload: any = {
      question_text: qform.question_text,
      question_type: qform.question_type,
      points: qform.points,
      position: list.length,
    };
    if (qform.question_type === "mcq") {
      payload.options = qform.options.filter((o) => o.text.trim());
      payload.correct_answer = qform.correct_answer;
    } else if (qform.question_type === "true_false") {
      payload.options = null;
      payload.correct_answer = qform.correct_answer;
    } else {
      payload.options = null;
      payload.correct_answer = qform.correct_answer || null;
    }
    addQuestion.mutate({ exam_id: examId, data: payload }, { onSuccess: resetQForm });
  };

  const questionList = questions as CBTQuestion[] | undefined;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft size={14} /> Back to exams
      </button>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900">{exam?.title || "Exam"}</h1>
          <p className="text-sm text-slate-500 mt-1">
            {questionList?.length ?? 0} questions · {exam?.total_points ?? 0} points
          </p>
        </div>
        {canWrite && !showForm && (
          <div className="flex gap-2">
            <button onClick={() => setShowBank(true)} className="btn-secondary gap-2">
              <FileQuestion size={15} />
              Add from bank
            </button>
            <button onClick={() => setShowForm(true)} className="btn-primary gap-2">
              <Plus size={15} />
              Add Question
            </button>
          </div>
        )}
      </div>

      {showBank && <BankPicker examId={examId} onClose={() => setShowBank(false)} />}

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Question</h2>
            <button onClick={resetQForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="space-y-4">
            <div>
              <label className="label">Question Text *</label>
              <textarea
                value={qform.question_text}
                onChange={(e) => setQform({ ...qform, question_text: e.target.value })}
                className="input"
                rows={2}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Type</label>
                <select
                  value={qform.question_type}
                  onChange={(e) => setQform({ ...qform, question_type: e.target.value as CBTQuestionType })}
                  className="input"
                >
                  <option value="mcq">Multiple Choice</option>
                  <option value="true_false">True / False</option>
                  <option value="short_answer">Short Answer</option>
                  <option value="long_answer">Long Answer</option>
                </select>
              </div>
              <div>
                <label className="label">Points</label>
                <input type="number" value={qform.points} onChange={(e) => setQform({ ...qform, points: Number(e.target.value) })} className="input" />
              </div>
            </div>

            {qform.question_type === "mcq" && (
              <div className="space-y-2">
                <label className="label">Options (pick correct with radio)</label>
                {qform.options.map((opt, i) => (
                  <div key={opt.key} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="correct"
                      checked={qform.correct_answer === opt.key}
                      onChange={() => setQform({ ...qform, correct_answer: opt.key })}
                    />
                    <span className="text-xs font-bold w-4">{opt.key}</span>
                    <input
                      value={opt.text}
                      onChange={(e) => {
                        const next = [...qform.options];
                        next[i] = { ...opt, text: e.target.value };
                        setQform({ ...qform, options: next });
                      }}
                      className="input flex-1"
                      placeholder={`Option ${opt.key}`}
                    />
                  </div>
                ))}
              </div>
            )}

            {qform.question_type === "true_false" && (
              <div>
                <label className="label">Correct Answer</label>
                <select value={qform.correct_answer} onChange={(e) => setQform({ ...qform, correct_answer: e.target.value })} className="input">
                  <option value="">Select…</option>
                  <option value="true">True</option>
                  <option value="false">False</option>
                </select>
              </div>
            )}

            {(qform.question_type === "short_answer" || qform.question_type === "long_answer") && (
              <div>
                <label className="label">Expected Answer (optional, for reference)</label>
                <textarea
                  value={qform.correct_answer}
                  onChange={(e) => setQform({ ...qform, correct_answer: e.target.value })}
                  className="input"
                  rows={2}
                />
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetQForm} className="btn-secondary">Cancel</button>
            <button onClick={handleAdd} disabled={addQuestion.isPending || !qform.question_text} className="btn-primary gap-2">
              {addQuestion.isPending && <Loader2 size={14} className="animate-spin" />}
              Add
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : questionList && questionList.length > 0 ? (
        <div className="space-y-3">
          {questionList.map((q, idx) => (
            <div key={q.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Q{idx + 1}</span>
                    <span className="badge bg-slate-50 text-slate-600 border-slate-200 text-[10px]">{q.question_type}</span>
                    <span className="text-xs text-slate-500">· {q.points} pts</span>
                  </div>
                  <p className="text-sm text-slate-900 mb-2">{q.question_text}</p>
                  {q.options && q.options.length > 0 && (
                    <ul className="space-y-1 mt-2">
                      {q.options.map((opt) => (
                        <li
                          key={opt.key}
                          className={cn(
                            "text-xs px-2 py-1 rounded",
                            q.correct_answer === opt.key ? "bg-emerald-50 text-emerald-700 font-semibold" : "text-slate-600",
                          )}
                        >
                          {opt.key}. {opt.text}
                        </li>
                      ))}
                    </ul>
                  )}
                  {q.correct_answer && q.question_type === "true_false" && (
                    <p className="text-xs text-emerald-700 font-semibold mt-2">Answer: {q.correct_answer}</p>
                  )}
                </div>
                {canWrite && (
                  <button
                    onClick={() => {
                      if (confirm("Delete this question?")) deleteQuestion.mutate(q.id);
                    }}
                    className="text-red-500 hover:text-red-700 p-1"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <FileQuestion size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No questions yet</p>
          <p className="text-sm mt-1">Add the first question to this exam.</p>
        </div>
      )}
    </div>
  );
}

interface PickBankItem { id: string; question_text: string; difficulty: string; subject_name: string | null; topic: string | null; points: number; }

function BankPicker({ examId, onClose }: { examId: string; onClose: () => void }) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { data, isLoading } = useBankItems({ search: search || undefined, page_size: 100 });
  const addFromBank = useAddFromBank();
  const items: PickBankItem[] = data?.items || [];

  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const add = () => addFromBank.mutate({ exam_id: examId, question_ids: [...selected] }, { onSuccess: onClose });

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h2 className="text-base font-bold text-slate-900">Add from Question Bank</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        </div>
        <div className="p-4 border-b border-slate-100">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search the bank…" className="input pl-9 w-full" autoFocus />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {isLoading ? (
            <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          ) : items.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-sm">
              No bank questions. Build the bank in <a href="/dashboard/modules/school/cbt/question-bank" className="text-brand-600 font-semibold hover:underline">Question Bank</a>.
            </div>
          ) : items.map((q) => (
            <label key={q.id} className="flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-50 cursor-pointer">
              <input type="checkbox" checked={selected.has(q.id)} onChange={() => toggle(q.id)} className="mt-1" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-800">{q.question_text}</p>
                <p className="text-[11px] text-slate-400 mt-0.5 capitalize">{q.difficulty}{q.subject_name ? ` · ${q.subject_name}` : ""}{q.topic ? ` · ${q.topic}` : ""} · {q.points} pt{q.points === 1 ? "" : "s"}</p>
              </div>
            </label>
          ))}
        </div>
        <div className="flex items-center justify-between p-4 border-t border-slate-100">
          <span className="text-xs text-slate-500">{selected.size} selected</span>
          <div className="flex gap-3">
            <button onClick={onClose} className="btn-secondary">Cancel</button>
            <button onClick={add} disabled={addFromBank.isPending || selected.size === 0} className="btn-primary gap-2">{addFromBank.isPending && <Loader2 size={15} className="animate-spin" />}Add {selected.size > 0 ? `(${selected.size})` : ""}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
