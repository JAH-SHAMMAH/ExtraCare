"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import DOMPurify from "dompurify";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TiptapLink from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import {
  useBankItems, useCreateBankItem, useUpdateBankItem, useDeleteBankItem, useImportBank,
} from "@/hooks/useSchoolExperience";
import { useSubjects } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import {
  FileQuestion, Eye, ChevronLeft, ChevronRight, Plus, Search, Upload, X, Loader2, Edit2, Trash2, ArrowLeft,
  Bold, Italic, Underline, List, ListOrdered, Link as LinkIcon, AlignLeft, AlignCenter, AlignRight, Undo2, Redo2,
} from "lucide-react";
import type { Subject } from "@/types";
import { renderQuestionHtml, sanitizeQuestionHtml } from "@/components/inputs/MathTools";
import { RichQuestionEditor } from "@/components/inputs/RichQuestionEditor";

const DIFFICULTIES = ["easy", "medium", "hard"];
const TYPES = [
  { value: "mcq", label: "Multiple choice" },
  { value: "true_false", label: "True / False" },
  { value: "short_answer", label: "Short answer" },
  { value: "long_answer", label: "Long answer" },
];
const DIFF_STYLE: Record<string, string> = {
  easy: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  hard: "bg-red-50 text-red-700 border-red-200",
};

const SANITIZE_CONFIG = {
  ALLOWED_TAGS: ["p", "br", "strong", "em", "u", "ol", "ul", "li", "a", "table", "tr", "td", "th", "thead", "tbody", "span"],
  ALLOWED_ATTR: ["href", "target", "data-latex", "class"],
  KEEP_CONTENT: true,
};

function sanitizeHTML(html: string): string {
  return DOMPurify.sanitize(html, SANITIZE_CONFIG);
}

interface BankItem {
  id: string; subject_id: string | null; subject_name: string | null; topic: string | null;
  difficulty: string; question_text: string; question_type: string;
  options: { key: string; text: string }[] | null; correct_answer: string | null; points: number;
  answer_type?: string; tags?: string[]; explanation?: string | null; is_examination?: boolean; created_by?: string | null;
}

export default function QuestionBankPage() {
  const [search, setSearch] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [editing, setEditing] = useState<BankItem | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [previewIdx, setPreviewIdx] = useState<number | null>(null);
  const [scope, setScope] = useState<"all" | "mine">("all");
  const [tag, setTag] = useState("");
  const [pageSize, setPageSize] = useState(50);
  const myId = (useAuthStore((st: any) => st.user) as any)?.id;
  const fileRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useBankItems({
    search: search || undefined, subject_id: subjectId || undefined, difficulty: difficulty || undefined, page_size: pageSize,
    mine: scope === "mine" || undefined, tag: tag.trim() || undefined,
  });
  const { data: subjectsData } = useSubjects();
  const subjects: Subject[] = subjectsData?.items || [];
  const importBank = useImportBank();
  const del = useDeleteBankItem();

  const items: BankItem[] = data?.items || [];

  const onImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) importBank.mutate(file);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <Link href="/dashboard/modules/school/cbt" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> CBT</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>CBT</span><span>/</span><span className="text-brand-600 font-semibold">Question Bank</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Question Bank</h1>
          <p className="text-slate-500 text-sm mt-0.5">Reusable questions you compose tests from. Categorised by subject, topic, and difficulty.</p>
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept=".csv" onChange={onImport} className="hidden" />
          <button onClick={() => fileRef.current?.click()} disabled={importBank.isPending} className="btn-secondary gap-2">
            {importBank.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} Import CSV
          </button>
          <button onClick={() => { setEditing(null); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> New Questions</button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search questions…" className="input pl-9 w-full" />
        </div>
        <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input w-auto">
          <option value="">All subjects</option>
          {subjects.map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}
        </select>
        <select aria-label="Question scope" value={scope} onChange={(e) => setScope(e.target.value as "all" | "mine")} className="input w-auto">
          <option value="all">All Questions</option>
          <option value="mine">My Questions</option>
        </select>
        <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="Tag" aria-label="Filter by tag" className="input w-28" />
        <select aria-label="Records per page" value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} className="input w-auto">
          {[10, 25, 50, 100].map((n) => (<option key={n} value={n}>{n} / page</option>))}
        </select>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="input w-auto capitalize">
          <option value="">All difficulty</option>
          {DIFFICULTIES.map((d) => (<option key={d} value={d}>{d}</option>))}
        </select>
      </div>

      {/* List */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center text-slate-400">
            <FileQuestion size={34} className="mx-auto mb-3 opacity-40" />
            <p className="font-semibold text-slate-500">No questions yet</p>
            <p className="text-sm mt-1">Add one, or import a CSV (columns: question, type, subject, topic, difficulty, option_a…e, correct_answer, points).</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-50">
            {items.map((q) => (
              <li key={q.id} className="px-5 py-3.5 flex items-start gap-3 hover:bg-slate-50/70 group">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-800 prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: renderQuestionHtml(q.question_text) }} />
                  <div className="flex flex-wrap items-center gap-2 mt-1.5">
                    <span className={cn("badge capitalize", DIFF_STYLE[q.difficulty] || "bg-slate-50 text-slate-600 border-slate-200")}>{q.difficulty}</span>
                    <span className="badge bg-slate-50 text-slate-500 border-slate-200">{TYPES.find((t) => t.value === q.question_type)?.label || q.question_type}{(q.question_type === "short_answer" || q.question_type === "long_answer") ? " (Subjective Question)" : ""}{q.answer_type === "file" ? " · File Upload" : ""}</span>
                    {myId && q.created_by === myId && <span className="badge bg-brand-50 text-brand-700 border-brand-200">My Questions</span>}
                    {q.is_examination && <span className="badge bg-purple-50 text-purple-700 border-purple-200">Examination</span>}
                    {(q.tags || []).map((t) => (<span key={t} className="badge bg-slate-50 text-slate-500 border-slate-200">#{t}</span>))}
                    {q.subject_name && <span className="text-[11px] text-slate-400">{q.subject_name}</span>}
                    {q.topic && <span className="text-[11px] text-slate-400">· {q.topic}</span>}
                    <span className="text-[11px] text-slate-400">· {q.points} pt{q.points === 1 ? "" : "s"}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button aria-label="Preview question" title="Preview" onClick={() => setPreviewIdx(items.indexOf(q))} className="p-1.5 rounded hover:bg-brand-50 text-slate-400 hover:text-brand-600"><Eye size={14} /></button>
                  <button aria-label="Edit question" title="Edit" onClick={() => { setEditing(q); setShowForm(true); }} className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"><Edit2 size={14} /></button>
                  <button aria-label="Delete question" title="Delete" onClick={() => { if (confirm("Delete this question from the bank?")) del.mutate(q.id); }} className="p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600"><Trash2 size={14} /></button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {previewIdx !== null && items[previewIdx] && (
        <PreviewModal
          items={items} index={previewIdx} onIndex={setPreviewIdx}
          onClose={() => setPreviewIdx(null)}
          onEdit={(q) => { setPreviewIdx(null); setEditing(q); setShowForm(true); }}
        />
      )}
      {showForm && <BankForm item={editing} subjects={subjects} topics={Array.from(new Set(items.map((q) => q.topic).filter(Boolean) as string[]))} onClose={() => setShowForm(false)} />}
    </div>
  );
}

function BankForm({ item, subjects, topics: existing, onClose }: { item: BankItem | null; subjects: Subject[]; topics: string[]; onClose: () => void }) {
  const [newTopics, setNewTopics] = useState<string[]>([]);
  const topics = Array.from(new Set([...existing, ...newTopics]));
  const create = useCreateBankItem();
  const update = useUpdateBankItem();
  const opt = (k: string) => item?.options?.find((o) => o.key === k)?.text || "";

  const [f, setF] = useState({
    question_text: item?.question_text || "",
    question_type: item?.question_type || "mcq",
    subject_id: item?.subject_id || "",
    topic: item?.topic || "",
    difficulty: item?.difficulty || "medium",
    points: String(item?.points ?? 1),
    options: (item?.options ? item.options.map((o: any, i: number) => ({ index: i, text: o.text })) : [
      { index: 0, text: "" },
      { index: 1, text: "" },
      { index: 2, text: "" },
      { index: 3, text: "" },
    ]) as any,
    correct_answer: /^\d+$/.test(item?.correct_answer || "") ? String.fromCharCode(97 + Number(item?.correct_answer)) : item?.correct_answer || "",
    answer_type: item?.answer_type || "text",
    showExplanation: !!item?.explanation,
    tags: (item?.tags || []).join(", "),
    explanation: item?.explanation || "",
    is_examination: !!item?.is_examination,
  });

  const isMcq = f.question_type === "mcq";
  const isTF = f.question_type === "true_false";

  const submit = () => {
    const options = isMcq
      ? f.options
          .filter((o) => o.text.trim())
          .map((o, i) => ({
            key: String.fromCharCode(97 + i), // a, b, c, ...
            text: o.text.trim()
          }))
      : undefined;
    const payload: any = {
      question_text: f.question_text.trim(),
      question_type: f.question_type,
      subject_id: f.subject_id || undefined,
      topic: f.topic.trim() || undefined,
      difficulty: f.difficulty,
      points: parseFloat(f.points) || 1,
      options,
      correct_answer: f.correct_answer.trim() || undefined,
      tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 20),
      explanation: f.showExplanation ? (f.explanation.trim() || undefined) : "",
      answer_type: f.question_type === "short_answer" || f.question_type === "long_answer" ? f.answer_type : "text",
      is_examination: f.is_examination,
    };
    const done = { onSuccess: onClose };
    if (item) update.mutate({ id: item.id, data: payload }, done);
    else create.mutate(payload, done);
  };

  const pending = create.isPending || update.isPending;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[88vh] overflow-y-auto shadow-2xl p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold text-slate-900">{item ? "Edit question" : "New question"}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
        </div>
        <div className="space-y-3">
          <RichQuestionEditor value={f.question_text} onChange={(html) => setF({ ...f, question_text: html })} />
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Type</label><select value={f.question_type} onChange={(e) => setF({ ...f, question_type: e.target.value })} className="input">{TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}</select></div>
            <div><label className="label">Difficulty</label><select value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })} className="input capitalize">{DIFFICULTIES.map((d) => (<option key={d} value={d}>{d}</option>))}</select></div>
            <div><label className="label">Subject</label><select value={f.subject_id} onChange={(e) => setF({ ...f, subject_id: e.target.value })} className="input"><option value="">—</option>{subjects.map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}</select></div>
            <div>
              <label className="label">Topic</label>
              <div className="flex gap-1">
                <input list="bank-topics" value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })} className="input flex-1" placeholder="Pick or type a topic" />
                <datalist id="bank-topics">{topics.map((t) => (<option key={t} value={t} />))}</datalist>
                <button type="button" title="Add topic" aria-label="Add topic" onClick={() => { const t = f.topic.trim(); if (t) setNewTopics((x) => (x.includes(t) ? x : [...x, t])); }} className="btn-secondary px-2"><Plus size={14} /></button>
              </div>
            </div>
          </div>

          {isMcq && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="label">Options</label>
                <button
                  type="button"
                  onClick={() => setF({
                    ...f,
                    options: [...f.options, { index: f.options.length, text: "" }] as any
                  })}
                  disabled={f.options.length >= 26}
                  className="text-xs text-brand-600 hover:underline disabled:opacity-50"
                >
                  + Add option
                </button>
              </div>
              {f.options.map((opt, idx) => (
                <div key={opt.index} className="flex items-center gap-2">
                  <span className="w-5 text-xs font-bold text-slate-400 uppercase">
                    {String.fromCharCode(65 + idx)}
                  </span>
                  <input
                    value={opt.text}
                    onChange={(e) => {
                      const newOpts = [...(f.options as any)];
                      newOpts[idx].text = e.target.value;
                      setF({ ...f, options: newOpts as any });
                    }}
                    className="input flex-1"
                    placeholder={`Option ${String.fromCharCode(65 + idx)}`}
                  />
                  {f.options.length > 2 && (
                    <button
                      type="button"
                      onClick={() => {
                        if (String.fromCharCode(97 + idx) === f.correct_answer) {
                          alert("Can't remove the correct answer option.");
                          return;
                        }
                        setF({
                          ...f,
                          options: (f.options as any).filter((o: any) => o.index !== opt.index) as any
                        });
                      }}
                      className="p-1 text-slate-400 hover:text-red-600"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Correct answer</label>
              {isMcq ? (
                <select value={f.correct_answer} onChange={(e) => setF({ ...f, correct_answer: e.target.value })} className="input">
                  <option value="">—</option>
                  {f.options.map((opt, idx) => (
                    <option key={opt.index} value={String.fromCharCode(97 + idx)}>
                      {String.fromCharCode(65 + idx)}
                    </option>
                  ))}
                </select>
              ) : isTF ? (
                <select value={f.correct_answer} onChange={(e) => setF({ ...f, correct_answer: e.target.value })} className="input"><option value="">—</option><option value="true">True</option><option value="false">False</option></select>
              ) : (
                <input value={f.correct_answer} onChange={(e) => setF({ ...f, correct_answer: e.target.value })} className="input" placeholder="Expected answer (optional)" />
              )}
            </div>
            <div><label className="label">Points</label><input type="number" min="0" step="0.5" value={f.points} onChange={(e) => setF({ ...f, points: e.target.value })} className="input" /></div>
          </div>
          <div><label className="label">Tags (comma separated)</label><input value={f.tags} onChange={(e) => setF({ ...f, tags: e.target.value })} className="input" placeholder="algebra, wassce" /></div>
          {(f.question_type === "short_answer" || f.question_type === "long_answer") && (
            <div><label className="label">Answer Option Type *</label>
              <select aria-label="Answer Option Type" value={f.answer_type} onChange={(e) => setF({ ...f, answer_type: e.target.value })} className="input">
                <option value="text">Text Box</option><option value="file">File Upload</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">How the student answers: type into a box, or upload a file (PDF, Word, photo).</p>
            </div>
          )}
          {!f.showExplanation ? (
            <button type="button" onClick={() => setF({ ...f, showExplanation: true })} className="inline-flex items-center gap-2 text-sm font-semibold text-amber-700 hover:underline"><Plus size={16} /> Add answer explanation</button>
          ) : (
            <div className="relative">
              <RichQuestionEditor label="Answer Explanation" value={f.explanation} onChange={(html) => setF((cur) => ({ ...cur, explanation: html }))} />
              <button type="button" aria-label="Remove answer explanation" title="Remove" onClick={() => setF({ ...f, showExplanation: false, explanation: "" })} className="absolute -top-1 right-0 text-red-600 hover:text-red-700"><X size={16} /></button>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={f.is_examination} onChange={(e) => setF({ ...f, is_examination: e.target.checked })} /> Is Examination question</label>
        </div>
        <div className="flex justify-end gap-3 mt-5">
          <button onClick={onClose} className="btn-secondary">Go Back</button>
          <button onClick={submit} disabled={pending || !f.question_text.trim()} className="btn-primary gap-2">{pending && <Loader2 size={15} className="animate-spin" />}{item ? "UPDATE" : "Add"}</button>
        </div>
      </div>
    </div>
  );
}

function PreviewModal({ items, index, onIndex, onClose, onEdit }: {
  items: BankItem[]; index: number; onIndex: (i: number) => void; onClose: () => void; onEdit: (q: BankItem) => void;
}) {
  const q = items[index];
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [seen, setSeen] = useState<Record<number, boolean>>({ [index]: true });
  const [secs, setSecs] = useState(0);
  useEffect(() => { const t = setInterval(() => setSecs((x) => x + 1), 1000); return () => clearInterval(t); }, []);
  const clock = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
  const go = (i: number) => { setSeen((s) => ({ ...s, [i]: true })); onIndex(i); };
  const opts = q.options || [];
  const subjective = q.question_type === "short_answer" || q.question_type === "long_answer";
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4" onClick={onClose} role="dialog" aria-label="Question preview">
      <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-bold text-slate-900">Question {index + 1} of {items.length}</h2>
          <span className="ml-auto mr-3 text-sm font-mono text-slate-500" aria-label="Preview timer">{clock}</span>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Close preview"><X size={18} /></button>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-4" aria-label="Question numbers">
          {items.map((_, i) => (
            <button key={i} onClick={() => go(i)} className={cn("w-7 h-7 rounded text-[11px] font-bold border",
              i === index ? "bg-brand-600 text-white border-brand-600" : picked[items[i].id] ? "bg-emerald-50 text-emerald-700 border-emerald-200" : seen[i] ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{i + 1}</button>
          ))}
        </div>
        <div className="flex gap-3 text-[10px] text-slate-400 mb-4">
          <span>■ Not attended</span><span className="text-amber-600">■ Viewed</span><span className="text-emerald-600">■ Attended</span><span className="text-brand-600">■ Selected</span>
        </div>
        <div className="text-sm text-slate-800 prose prose-sm max-w-none mb-4" dangerouslySetInnerHTML={{ __html: renderQuestionHtml(q.question_text) }} />
        {subjective ? (
          <textarea className="input w-full min-h-[90px]" placeholder="Student's answer appears here" value={picked[q.id] || ""} onChange={(e) => setPicked({ ...picked, [q.id]: e.target.value })} />
        ) : (
          <div className="space-y-2">
            {(q.question_type === "true_false" && opts.length === 0 ? [{ key: "true", text: "True" }, { key: "false", text: "False" }] : opts).map((o) => (
              <label key={o.key} className={cn("flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer text-sm", picked[q.id] === o.key ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:bg-slate-50")}>
                <input type="radio" name="preview-opt" checked={picked[q.id] === o.key} onChange={() => setPicked({ ...picked, [q.id]: o.key })} />
                <span className="font-bold uppercase text-slate-400 w-4">{o.key}</span><span>{o.text}</span>
              </label>
            ))}
          </div>
        )}
        {q.explanation && <div className="mt-4 text-xs text-slate-500 prose prose-sm max-w-none"><span className="font-semibold">Explanation: </span><span dangerouslySetInnerHTML={{ __html: renderQuestionHtml(q.explanation) }} /></div>}
        <div className="flex flex-wrap items-center justify-between gap-2 mt-6">
          <div className="flex gap-2">
            <button disabled={index === 0} onClick={() => go(index - 1)} className="btn-secondary gap-1"><ChevronLeft size={14} /> Previous</button>
            <button disabled={index >= items.length - 1} onClick={() => go(index + 1)} className="btn-secondary gap-1">Next <ChevronRight size={14} /></button>
            <button onClick={() => { const { [q.id]: _x, ...rest } = picked; setPicked(rest); }} className="btn-secondary">Reset Answer</button>
          </div>
          <div className="flex gap-2">
            <button onClick={() => onEdit(q)} className="btn-secondary gap-1"><Edit2 size={14} /> Edit Question</button>
            <button onClick={onClose} className="btn-primary">Stop Preview</button>
          </div>
        </div>
      </div>
    </div>
  );
}
