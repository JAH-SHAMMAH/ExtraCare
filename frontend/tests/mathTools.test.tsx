// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import katex from "katex";
import "katex/contrib/mhchem";
import { renderQuestionHtml, sanitizeQuestionHtml } from "@/components/inputs/MathTools";

describe("question html", () => {
  it("renders a stored formula with KaTeX", () => {
    expect(renderQuestionHtml('<p>Solve <span class="math-tex" data-latex="\\frac{a}{b}">x</span></p>')).toContain("katex");
  });
  it("strips event handlers", () => {
    const out = renderQuestionHtml('<p onclick="x()">hi<span data-latex="x" onmouseover="y()"></span></p>');
    expect(out).not.toContain("onclick");
    expect(out).not.toContain("onmouseover");
  });
  it("keeps whitelisted formatting, drops dangerous styles and image sources", () => {
    const out = sanitizeQuestionHtml(
      '<h2 style="text-align:center">T</h2><span style="color:#f00;font-family:Georgia;font-size:14pt">a</span>' +
      '<span style="background:url(http://evil)">b</span><img src="javascript:alert(1)"><img src="https://cdn/x.png">' +
      '<sub>2</sub><sup>3</sup><table><tr><td colspan="2">c</td></tr></table>');
    expect(out).toContain("text-align");
    expect(out).toContain("font-family");
    expect(out).not.toContain("evil");
    expect(out).not.toContain("javascript");
    expect(out).toContain("https://cdn/x.png");
    expect(out).toContain("<sub>");
    expect(out).toContain("<table");
  });
});

describe("formula samples compile", () => {
  const samples = [
    "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}", "\\sum_{i=1}^{n} i", "\\int_{a}^{b} f(x)\\,dx", "\\lim_{x\\to 0}\\frac{\\sin x}{x}",
    "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}", "\\begin{cases} x & x>0 \\\\ -x & x\\le 0 \\end{cases}",
    "\\ce{2H2 + O2 -> 2H2O}", "\\ce{SO4^2-}", "{}^{n}C_{r}", "\\mathbb{R}", "\\vec{v}", "\\tfrac{1}{3}",
  ];
  for (const s of samples) it(s, () => { expect(() => katex.renderToString(s, { throwOnError: true })).not.toThrow(); });
});
