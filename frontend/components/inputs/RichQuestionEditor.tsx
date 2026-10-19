"use client";

import { useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TiptapLink from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import Image from "@tiptap/extension-image";
import { TextStyle, Color, FontFamily, FontSize } from "@tiptap/extension-text-style";
import { TableKit } from "@tiptap/extension-table";
import {
  Bold, Italic, Underline as UnderlineIcon, List, ListOrdered, Link as LinkIcon, AlignLeft, AlignCenter, AlignRight,
  AlignJustify, Undo2, Redo2, Quote, ImagePlus, Table as TableIcon, Omega, Subscript as SubIcon, Superscript as SupIcon, Loader2, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { uploadApi } from "@/lib/api";
import { MathInline, FormulaDialog, sanitizeQuestionHtml } from "@/components/inputs/MathTools";

const FONTS = ["Arial", "Comic Sans MS", "Courier New", "Georgia", "Times New Roman", "Verdana", "Tahoma", "Trebuchet MS"];
const SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72];
const COLORS = ["#000000", "#475569", "#dc2626", "#ea580c", "#ca8a04", "#16a34a", "#0891b2", "#2563eb", "#7c3aed", "#db2777"];
const SPECIAL = "© ® ™ § ¶ † ‡ • … ‰ ′ ″ ¼ ½ ¾ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁰ ₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉ ± × ÷ ≤ ≥ ≠ ≈ ∞ √ ∑ ∏ ∫ ∂ ∆ ∇ ∈ ∉ ∪ ∩ ⊂ ⊃ ∅ ∴ ∵ → ← ↑ ↓ ↔ ⇒ ⇔ ° µ Ω α β γ δ ε θ λ π σ φ ψ ω £ € ₦ $ ¢ ¥ « » “ ” ‘ ’ – — ¿ ¡ é è ê ë á à â ä í ó ö ú ü ñ ç".split(" ");

const BTN = "p-2 rounded hover:bg-slate-200 transition disabled:opacity-40";

export function RichQuestionEditor({ value, onChange, label = "Question *" }: {
  value: string; onChange: (html: string) => void; label?: string;
}) {
  const [formula, setFormula] = useState(false);
  const [special, setSpecial] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({ link: false } as any),
      TiptapLink.configure({ openOnClick: false }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Subscript, Superscript,
      TextStyle, Color, FontFamily, FontSize,
      Image.configure({ inline: true }),
      TableKit.configure({ table: { resizable: false } }),
      MathInline,
    ],
    content: value,
    onUpdate: ({ editor }) => onChange(sanitizeQuestionHtml(editor.getHTML())),
  });
  if (!editor) return null;

  const block = editor.isActive("heading", { level: 1 }) ? "h1" : editor.isActive("heading", { level: 2 }) ? "h2"
    : editor.isActive("heading", { level: 3 }) ? "h3" : editor.isActive("codeBlock") ? "pre" : "p";
  const setBlock = (v: string) => {
    const c = editor.chain().focus();
    if (v === "p") c.setParagraph().run();
    else if (v === "pre") c.setCodeBlock().run();
    else c.setHeading({ level: Number(v[1]) as 1 | 2 | 3 }).run();
  };
  const attrs = editor.getAttributes("textStyle") as { fontFamily?: string; fontSize?: string; color?: string };
  const curSize = (attrs.fontSize || "").replace("pt", "");

  const pickImage = async (f?: File) => {
    if (!f) return;
    setErr(""); setUploading(true);
    try {
      const { url } = await uploadApi.questionImage(f);
      editor.chain().focus().setImage({ src: url, alt: "" }).run();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Image upload failed.");
    } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const T = ({ on, active, title, children, disabled }: { on: () => void; active?: boolean; title: string; children: React.ReactNode; disabled?: boolean }) => (
    <button type="button" title={title} aria-label={title} disabled={disabled} onClick={on} className={cn(BTN, active && "bg-slate-200")}>{children}</button>
  );
  const Sep = () => <div className="w-px bg-slate-300 mx-1 self-stretch" />;

  return (
    <div>
      <label className="label">{label}</label>
      <div className="border border-b-0 border-slate-200 rounded-t-lg bg-slate-50 p-2 space-y-1">
        <div className="flex flex-wrap gap-2">
          <select aria-label="Paragraph format" value={block} onChange={(e) => setBlock(e.target.value)} className="input w-auto py-1 text-sm">
            <option value="p">Normal</option><option value="h1">Heading 1</option><option value="h2">Heading 2</option>
            <option value="h3">Heading 3</option><option value="pre">Formatted</option>
          </select>
          <select aria-label="Font size" value={curSize} onChange={(e) => (e.target.value ? editor.chain().focus().setFontSize(`${e.target.value}pt`).run() : editor.chain().focus().unsetFontSize().run())} className="input w-auto py-1 text-sm">
            <option value="">Size</option>{SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <select aria-label="Font" value={attrs.fontFamily || ""} onChange={(e) => (e.target.value ? editor.chain().focus().setFontFamily(e.target.value).run() : editor.chain().focus().unsetFontFamily().run())} className="input w-auto py-1 text-sm">
            <option value="">Font</option>{FONTS.map((f) => <option key={f} value={f} style={{ fontFamily: f }}>{f}</option>)}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-0.5">
          <T title="Bold" active={editor.isActive("bold")} on={() => editor.chain().focus().toggleBold().run()}><Bold size={14} /></T>
          <T title="Italic" active={editor.isActive("italic")} on={() => editor.chain().focus().toggleItalic().run()}><Italic size={14} /></T>
          <T title="Underline" active={editor.isActive("underline")} on={() => editor.chain().focus().toggleUnderline().run()}><UnderlineIcon size={14} /></T>
          <label className={cn(BTN, "cursor-pointer relative inline-flex items-center")} title="Text colour">
            <span className="font-black text-sm leading-none" style={{ borderBottom: `3px solid ${attrs.color || "#000"}` }}>A</span>
            <select aria-label="Text colour" value={attrs.color || ""} onChange={(e) => (e.target.value ? editor.chain().focus().setColor(e.target.value).run() : editor.chain().focus().unsetColor().run())} className="absolute inset-0 opacity-0 cursor-pointer">
              <option value="">Default</option>{COLORS.map((c) => <option key={c} value={c} style={{ color: c }}>{c}</option>)}
            </select>
          </label>
          <T title="Subscript" active={editor.isActive("subscript")} on={() => editor.chain().focus().toggleSubscript().run()}><SubIcon size={14} /></T>
          <T title="Superscript" active={editor.isActive("superscript")} on={() => editor.chain().focus().toggleSuperscript().run()}><SupIcon size={14} /></T>
          <Sep />
          <T title="Align left" active={editor.isActive({ textAlign: "left" })} on={() => editor.chain().focus().setTextAlign("left").run()}><AlignLeft size={14} /></T>
          <T title="Align centre" active={editor.isActive({ textAlign: "center" })} on={() => editor.chain().focus().setTextAlign("center").run()}><AlignCenter size={14} /></T>
          <T title="Align right" active={editor.isActive({ textAlign: "right" })} on={() => editor.chain().focus().setTextAlign("right").run()}><AlignRight size={14} /></T>
          <T title="Justify" active={editor.isActive({ textAlign: "justify" })} on={() => editor.chain().focus().setTextAlign("justify").run()}><AlignJustify size={14} /></T>
          <Sep />
          <T title="Bullet list" active={editor.isActive("bulletList")} on={() => editor.chain().focus().toggleBulletList().run()}><List size={14} /></T>
          <T title="Numbered list" active={editor.isActive("orderedList")} on={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered size={14} /></T>
          <Sep />
          <T title="Link" active={editor.isActive("link")} on={() => { const url = window.prompt("Enter URL (https://…):"); if (url && /^(https?:\/\/|mailto:)/i.test(url)) editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run(); }}><LinkIcon size={14} /></T>
          <T title="Quote" active={editor.isActive("blockquote")} on={() => editor.chain().focus().toggleBlockquote().run()}><Quote size={14} /></T>
          <T title="Insert image" disabled={uploading} on={() => fileRef.current?.click()}>{uploading ? <Loader2 size={14} className="animate-spin" /> : <ImagePlus size={14} />}</T>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={(e) => pickImage(e.target.files?.[0])} />
          <T title="Insert table" on={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}><TableIcon size={14} /></T>
          <T title="Special characters" on={() => setSpecial(true)}><Omega size={14} /></T>
          <T title="Insert formula" on={() => setFormula(true)}><span className="font-black text-sm text-red-700 leading-none px-0.5">∑ Formula</span></T>
          <Sep />
          <T title="Undo" disabled={!editor.can().undo()} on={() => editor.chain().focus().undo().run()}><Undo2 size={14} /></T>
          <T title="Redo" disabled={!editor.can().redo()} on={() => editor.chain().focus().redo().run()}><Redo2 size={14} /></T>
        </div>
        {editor.isActive("table") && (
          <div className="flex flex-wrap gap-1 text-xs pt-1" aria-label="Table tools">
            {[["Row above", () => editor.chain().focus().addRowBefore().run()], ["Row below", () => editor.chain().focus().addRowAfter().run()],
              ["Column left", () => editor.chain().focus().addColumnBefore().run()], ["Column right", () => editor.chain().focus().addColumnAfter().run()],
              ["Delete row", () => editor.chain().focus().deleteRow().run()], ["Delete column", () => editor.chain().focus().deleteColumn().run()],
              ["Delete table", () => editor.chain().focus().deleteTable().run()]].map(([l, f]) => (
              <button key={l as string} type="button" onClick={f as () => void} className="px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-100">{l as string}</button>
            ))}
          </div>
        )}
        {err && <p className="text-xs text-red-600">{err}</p>}
      </div>
      <div className="border border-slate-200 rounded-b-lg overflow-hidden prose prose-sm max-w-none rich-question">
        <EditorContent editor={editor} className="p-3 min-h-[120px] bg-white text-slate-700 focus:outline-none" />
      </div>
      {formula && <FormulaDialog onClose={() => setFormula(false)} onInsert={(latex) => { editor.chain().focus().insertContent({ type: "mathInline", attrs: { latex } }).run(); setFormula(false); }} />}
      {special && (
        <div className="fixed inset-0 z-[60] bg-slate-900/50 flex items-center justify-center p-4" onClick={() => setSpecial(false)} role="dialog" aria-label="Special characters">
          <div className="bg-white rounded-2xl w-full max-w-md p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3"><h3 className="font-bold text-slate-900">Special characters</h3><button aria-label="Close" onClick={() => setSpecial(false)} className="text-slate-400"><X size={18} /></button></div>
            <div className="grid grid-cols-8 gap-1">
              {SPECIAL.map((c, i) => (
                <button key={i} type="button" onClick={() => { editor.chain().focus().insertContent(c).run(); setSpecial(false); }} className="h-9 rounded border border-slate-200 hover:bg-brand-50 text-base">{c}</button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
