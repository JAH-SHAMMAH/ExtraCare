"use client";

import { useRef, useState } from "react";
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
import {
  FileQuestion, Plus, Search, Upload, X, Loader2, Edit2, Trash2, ArrowLeft,
  Bold, Italic, Underline, List, ListOrdered, Link as LinkIcon, AlignLeft, AlignCenter, AlignRight, Undo2, Redo2,
} from "lucide-react";
import type { Subject } from "@/types";

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
  ALLOWED_TAGS: ["p", "br", "strong", "em", "u", "ol", "ul", "li", "a", "table", "tr", "td", "th", "thead", "tbody"],
  ALLOWED_ATTR: ["href", "target"],
  KEEP_CONTENT: true,
};

function sanitizeHTML(html: string): string {
  return DOMPurify.sanitize(html, SANITIZE_CONFIG);
}

interface BankItem {
  id: string; subject_id: string | null; subject_name: string | null; topic: string | null;
  difficulty: string; question_text: string; question_type: string;
  options: { key: string; text: string }[] | null; correct_answer: string | null; points: number;
}

export default function QuestionBankPage() {
  const [search, setSearch] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [editing, setEditing] = useState<BankItem | null>(null);
  const [showForm, setShowForm] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useBankItems({
    search: search || undefined, subject_id: subjectId || undefined, difficulty: difficulty || undefined, page_size: 100,
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
          <button onClick={() => { setEditing(null); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Add Question</button>
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
                  <div className="text-sm font-medium text-slate-800 prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: sanitizeHTML(q.question_text) }} />
                  <div className="flex flex-wrap items-center gap-2 mt-1.5">
                    <span className={cn("badge capitalize", DIFF_STYLE[q.difficulty] || "bg-slate-50 text-slate-600 border-slate-200")}>{q.difficulty}</span>
                    <span className="badge bg-slate-50 text-slate-500 border-slate-200">{TYPES.find((t) => t.value === q.question_type)?.label || q.question_type}</span>
                    {q.subject_name && <span className="text-[11px] text-slate-400">{q.subject_name}</span>}
                    {q.topic && <span className="text-[11px] text-slate-400">· {q.topic}</span>}
                    <span className="text-[11px] text-slate-400">· {q.points} pt{q.points === 1 ? "" : "s"}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => { setEditing(q); setShowForm(true); }} className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"><Edit2 size={14} /></button>
                  <button onClick={() => { if (confirm("Delete this question from the bank?")) del.mutate(q.id); }} className="p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600"><Trash2 size={14} /></button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showForm && <BankForm item={editing} subjects={subjects} onClose={() => setShowForm(false)} />}
    </div>
  );
}

function BankForm({ item, subjects, onClose }: { item: BankItem | null; subjects: Subject[]; onClose: () => void }) {
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
    correct_answer: item?.correct_answer || "",
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
          <QuestionEditor value={f.question_text} onChange={(html) => setF({ ...f, question_text: html })} />
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Type</label><select value={f.question_type} onChange={(e) => setF({ ...f, question_type: e.target.value })} className="input">{TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}</select></div>
            <div><label className="label">Difficulty</label><select value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })} className="input capitalize">{DIFFICULTIES.map((d) => (<option key={d} value={d}>{d}</option>))}</select></div>
            <div><label className="label">Subject</label><select value={f.subject_id} onChange={(e) => setF({ ...f, subject_id: e.target.value })} className="input"><option value="">—</option>{subjects.map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}</select></div>
            <div><label className="label">Topic</label><input value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })} className="input" /></div>
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
                        if (String(idx) === f.correct_answer) {
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
                    <option key={opt.index} value={String(idx)}>
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
        </div>
        <div className="flex justify-end gap-3 mt-5">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={submit} disabled={pending || !f.question_text.trim()} className="btn-primary gap-2">{pending && <Loader2 size={15} className="animate-spin" />}{item ? "Save" : "Add"}</button>
        </div>
      </div>
    </div>
  );
}

function QuestionEditor({ value, onChange }: { value: string; onChange: (html: string) => void }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      TiptapLink.configure({ openOnClick: false }),
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
      <label className="label">Question *</label>
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
          className="p-3 min-h-[80px] bg-white text-slate-700 focus:outline-none"
        />
      </div>
    </div>
  );
}
