"use client";

import { useEffect, useMemo, useState } from "react";
import DOMPurify from "dompurify";
import katex from "katex";
import "katex/contrib/mhchem";
import "katex/dist/katex.min.css";
import { Node, mergeAttributes } from "@tiptap/react";
import { X } from "lucide-react";

// ── Storage format ────────────────────────────────────────────────────────────
// A formula is stored as <span class="math-tex" data-latex="...">…</span>. Only
// the LaTeX source is trusted data; the visual is re-rendered by KaTeX on show,
// so stored HTML never carries rendered markup (nothing to sanitise but text).

export const MathInline = Node.create({
  name: "mathInline",
  group: "inline",
  inline: true,
  atom: true,
  addAttributes() {
    return {
      latex: {
        default: "",
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-latex") || "",
        renderHTML: (attrs) => ({ "data-latex": attrs.latex }),
      },
    };
  },
  parseHTML() { return [{ tag: "span[data-latex]" }]; },
  renderHTML({ HTMLAttributes, node }) {
    return ["span", mergeAttributes({ class: "math-tex" }, HTMLAttributes), `\\(${node.attrs.latex}\\)`];
  },
  addNodeView() {
    return ({ node }) => {
      const dom = document.createElement("span");
      dom.className = "math-tex";
      dom.setAttribute("data-latex", node.attrs.latex);
      try { dom.innerHTML = katex.renderToString(node.attrs.latex, { throwOnError: false, trust: false }); }
      catch { dom.textContent = node.attrs.latex; }
      return { dom };
    };
  },
});

// A private DOMPurify instance so the strict style/src hooks never affect other pages.
let _purify: any = null;
function purifier() {
  if (_purify) return _purify;
  const p = (DOMPurify as any)(window);
  const FONTS = ["arial", "comic sans ms", "courier new", "georgia", "times new roman", "verdana", "tahoma", "trebuchet ms", "sans-serif", "serif", "monospace", "cursive"];
  const colorRe = /^(#[0-9a-f]{3,8}|rgba?\(\s*\d{1,3}\s*(,\s*\d{1,3}\s*){2}(,\s*[0-9.]+\s*)?\)|[a-z]{3,20})$/i;
  const sizeRe = /^\d{1,3}(\.\d+)?(px|pt|em|rem|%)$/;
  const styleOk = (v: string) => v.split(";").map((d) => d.trim()).filter(Boolean).every((d) => {
    const i = d.indexOf(":"); if (i < 0) return false;
    const prop = d.slice(0, i).trim().toLowerCase(); const val = d.slice(i + 1).trim().replace(/^["']|["']$/g, "");
    if (prop === "color" || prop === "background-color") return colorRe.test(val);
    if (prop === "font-size" || prop === "width" || prop === "min-width") return sizeRe.test(val);
    if (prop === "font-family") return val.split(",").every((f) => FONTS.includes(f.trim().replace(/^["']|["']$/g, "").toLowerCase()));
    if (prop === "text-align") return ["left", "right", "center", "justify"].includes(val);
    return false;
  });
  p.addHook("uponSanitizeAttribute", (_node: Element, data: any) => {
    const n = data.attrName; const v = String(data.attrValue || "");
    if (n === "style" && !styleOk(v)) data.keepAttr = false;
    if (n === "src" && !/^(https:\/\/|\/)/.test(v)) data.keepAttr = false;
    if (n === "class" && v !== "math-tex") data.keepAttr = false;
    if (n === "data-latex" && v.length > 2000) data.keepAttr = false;
  });
  _purify = p;
  return p;
}

const SANITIZE = {
  ALLOWED_TAGS: ["p", "br", "strong", "em", "u", "ol", "ul", "li", "a", "span", "sub", "sup", "blockquote", "pre", "code",
    "h1", "h2", "h3", "img", "hr", "table", "colgroup", "col", "tr", "td", "th", "thead", "tbody"],
  ALLOWED_ATTR: ["href", "target", "data-latex", "class", "style", "src", "alt", "width", "height", "colspan", "rowspan", "colwidth"],
  KEEP_CONTENT: true,
};

export function sanitizeQuestionHtml(html: string): string {
  if (typeof window === "undefined") return html || "";
  return purifier().sanitize(html || "", SANITIZE) as string;
}

/** Sanitise question HTML and render every formula span with KaTeX. */
export function renderQuestionHtml(html: string): string {
  const clean = sanitizeQuestionHtml(html);
  if (typeof document === "undefined" || !clean.includes("data-latex")) return clean;
  const box = document.createElement("div");
  box.innerHTML = clean;
  box.querySelectorAll("span[data-latex]").forEach((el) => {
    const src = el.getAttribute("data-latex") || "";
    try { el.innerHTML = katex.renderToString(src, { throwOnError: false, trust: false }); }
    catch { el.textContent = src; }
  });
  return box.innerHTML;
}

const PALETTES: Record<string, { label: string; tex: string }[]> = {
  Basic: [
    { label: "a/b", tex: "\\frac{a}{b}" }, { label: "√", tex: "\\sqrt{x}" }, { label: "ⁿ√", tex: "\\sqrt[n]{x}" },
    { label: "x²", tex: "x^{2}" }, { label: "xₙ", tex: "x_{n}" }, { label: "xₙʸ", tex: "x_{n}^{y}" },
    { label: "±", tex: "\\pm" }, { label: "∓", tex: "\\mp" }, { label: "×", tex: "\\times" }, { label: "÷", tex: "\\div" },
    { label: "·", tex: "\\cdot" }, { label: "≤", tex: "\\le" }, { label: "≥", tex: "\\ge" }, { label: "≠", tex: "\\neq" },
    { label: "≈", tex: "\\approx" }, { label: "≡", tex: "\\equiv" }, { label: "∝", tex: "\\propto" }, { label: "%", tex: "\\%" },
    { label: "(  )", tex: "\\left( x \\right)" }, { label: "[  ]", tex: "\\left[ x \\right]" }, { label: "{  }", tex: "\\left\\{ x \\right\\}" },
    { label: "|x|", tex: "\\left| x \\right|" }, { label: "°", tex: "^{\\circ}" }, { label: "x̄", tex: "\\bar{x}" },
    { label: "ⁿCᵣ", tex: "{}^{n}C_{r}" }, { label: "ⁿPᵣ", tex: "{}^{n}P_{r}" }, { label: "log", tex: "\\log_{b}" }, { label: "ln", tex: "\\ln" },
    { label: "eˣ", tex: "e^{x}" }, { label: "mixed", tex: "2\\tfrac{1}{3}" },
  ],
  Greek: ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Phi", "Psi", "Omega"].map((n) => ({
    label: ({ alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", zeta: "ζ", eta: "η", theta: "θ", iota: "ι", kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π", rho: "ρ", sigma: "σ", tau: "τ", upsilon: "υ", phi: "φ", chi: "χ", psi: "ψ", omega: "ω",
      Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω" } as Record<string, string>)[n],
    tex: `\\${n}`,
  })),
  Calculus: [
    { label: "∑", tex: "\\sum_{i=1}^{n}" }, { label: "∏", tex: "\\prod_{i=1}^{n}" }, { label: "∫", tex: "\\int_{a}^{b} f(x)\\,dx" },
    { label: "∬", tex: "\\iint" }, { label: "∮", tex: "\\oint" }, { label: "lim", tex: "\\lim_{x\\to 0}" },
    { label: "d/dx", tex: "\\frac{d}{dx}" }, { label: "∂/∂x", tex: "\\frac{\\partial}{\\partial x}" }, { label: "∇", tex: "\\nabla" },
    { label: "∞", tex: "\\infty" }, { label: "Δx", tex: "\\Delta x" }, { label: "f′", tex: "f'(x)" },
  ],
  Trig: [
    { label: "sin", tex: "\\sin\\theta" }, { label: "cos", tex: "\\cos\\theta" }, { label: "tan", tex: "\\tan\\theta" },
    { label: "cot", tex: "\\cot\\theta" }, { label: "sec", tex: "\\sec\\theta" }, { label: "csc", tex: "\\csc\\theta" },
    { label: "sin⁻¹", tex: "\\sin^{-1}" }, { label: "cos⁻¹", tex: "\\cos^{-1}" }, { label: "tan⁻¹", tex: "\\tan^{-1}" },
    { label: "sinh", tex: "\\sinh" }, { label: "cosh", tex: "\\cosh" }, { label: "tanh", tex: "\\tanh" },
  ],
  Sets: [
    { label: "∈", tex: "\\in" }, { label: "∉", tex: "\\notin" }, { label: "⊂", tex: "\\subset" }, { label: "⊆", tex: "\\subseteq" },
    { label: "∪", tex: "\\cup" }, { label: "∩", tex: "\\cap" }, { label: "∅", tex: "\\emptyset" }, { label: "ℝ", tex: "\\mathbb{R}" },
    { label: "ℕ", tex: "\\mathbb{N}" }, { label: "ℤ", tex: "\\mathbb{Z}" }, { label: "ℚ", tex: "\\mathbb{Q}" }, { label: "ℂ", tex: "\\mathbb{C}" },
    { label: "∀", tex: "\\forall" }, { label: "∃", tex: "\\exists" }, { label: "∴", tex: "\\therefore" }, { label: "∵", tex: "\\because" },
    { label: "∧", tex: "\\land" }, { label: "∨", tex: "\\lor" }, { label: "¬", tex: "\\neg" }, { label: "⇒", tex: "\\Rightarrow" }, { label: "⇔", tex: "\\Leftrightarrow" },
  ],
  Arrows: [
    { label: "→", tex: "\\rightarrow" }, { label: "←", tex: "\\leftarrow" }, { label: "↔", tex: "\\leftrightarrow" },
    { label: "↑", tex: "\\uparrow" }, { label: "↓", tex: "\\downarrow" }, { label: "⇌", tex: "\\rightleftharpoons" },
    { label: "⟶", tex: "\\longrightarrow" }, { label: "↦", tex: "\\mapsto" },
  ],
  Matrices: [
    { label: "2×2 ( )", tex: "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}" },
    { label: "3×3 ( )", tex: "\\begin{pmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{pmatrix}" },
    { label: "2×2 [ ]", tex: "\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}" },
    { label: "det | |", tex: "\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}" },
    { label: "cases", tex: "\\begin{cases} x & x>0 \\\\ -x & x\\le 0 \\end{cases}" },
    { label: "align", tex: "\\begin{aligned} a &= b + c \\\\ &= d \\end{aligned}" },
  ],
  Chemistry: [
    { label: "H₂O", tex: "\\ce{H2O}" }, { label: "CO₂", tex: "\\ce{CO2}" }, { label: "SO₄²⁻", tex: "\\ce{SO4^2-}" },
    { label: "A → B", tex: "\\ce{A -> B}" }, { label: "⇌", tex: "\\ce{A <=> B}" }, { label: "2H₂+O₂→2H₂O", tex: "\\ce{2H2 + O2 -> 2H2O}" },
    { label: "Na⁺", tex: "\\ce{Na+}" }, { label: "Δ", tex: "\\ce{A ->[\\Delta] B}" },
  ],
};

/** Formula editor dialog: palette + LaTeX box + live preview (FMath-style). */
export function FormulaDialog({ initial = "", onInsert, onClose }: {
  initial?: string; onInsert: (latex: string) => void; onClose: () => void;
}) {
  const [tex, setTex] = useState(initial);
  const [tab, setTab] = useState("Basic");
  const [err, setErr] = useState("");
  const preview = useMemo(() => {
    try { setErr(""); return katex.renderToString(tex || "\\ ", { throwOnError: true, trust: false, displayMode: true }); }
    catch (e: any) { return ""; }
  }, [tex]);
  useEffect(() => {
    try { katex.renderToString(tex || "x", { throwOnError: true }); setErr(""); }
    catch (e: any) { setErr(String(e.message || "Invalid formula").replace(/^KaTeX parse error: /, "")); }
  }, [tex]);
  return (
    <div className="fixed inset-0 z-[60] bg-slate-900/50 flex items-center justify-center p-4" onClick={onClose} role="dialog" aria-label="Formula editor">
      <div className="bg-white rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-slate-900">Formula editor</h3>
          <button onClick={onClose} aria-label="Close" className="text-slate-400"><X size={18} /></button>
        </div>
        <div className="flex flex-wrap gap-1 mb-2" role="tablist">
          {Object.keys(PALETTES).map((k) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
              className={"px-2.5 py-1 rounded-t text-xs font-semibold " + (tab === k ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>{k}</button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1 mb-3">
          {PALETTES[tab].map((b) => (
            <button key={b.label} type="button" title={b.tex} onClick={() => setTex((t) => t + b.tex)}
              className="min-w-[34px] h-8 px-2 rounded border border-slate-200 bg-slate-50 hover:bg-brand-50 text-sm">{b.label}</button>
          ))}
        </div>
        <textarea aria-label="LaTeX" value={tex} onChange={(e) => setTex(e.target.value)} rows={3}
          className="input w-full font-mono text-sm" placeholder="x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}" />
        <div className="mt-3 border border-slate-200 rounded-lg p-3 min-h-[70px] overflow-x-auto bg-white" aria-label="Formula preview"
          dangerouslySetInnerHTML={{ __html: preview }} />
        {err && <p className="text-xs text-red-600 mt-1">{err}</p>}
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button disabled={!tex.trim() || !!err} onClick={() => onInsert(tex.trim())} className="btn-primary">Insert formula</button>
        </div>
      </div>
    </div>
  );
}
