"use client";

import { useState } from "react";
import {
  useSections, useReportTemplates, useUpdateTemplate,
  useGradingScales, useReplaceScaleBands, useBootstrapReportConfig,
} from "@/hooks/usePlatform";
import { Loader2, Trash2, Plus, Wand2, FileText, Save } from "lucide-react";
import type { ReportTemplate, GradingScale } from "@/types";

/**
 * School Reports R2 config — report templates + grading scales (per section).
 * Sections/divisions themselves are managed on the "School Types" tab. Every
 * number here (grading bands, CA/exam weights) is editable data — seeded values
 * are flagged provisional until the school enters real figures, so a report never
 * prints a hardcoded boundary.
 */
export function ReportConfig({ canWrite }: { canWrite: boolean }) {
  const { data: sections = [], isLoading } = useSections();
  const { data: templates = [] } = useReportTemplates();
  const { data: scales = [] } = useGradingScales();
  const bootstrap = useBootstrapReportConfig();

  if (isLoading) return <div className="py-16 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>;

  const empty = sections.length === 0 && templates.length === 0;

  return (
    <div className="space-y-8">
      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-xs text-amber-800">
        Numbers here (grading bands, CA/exam weights) are <strong>editable data, not fixed</strong>. Seeded values are marked <em>provisional</em> until you enter the school&apos;s real figures &mdash; a report never prints a hardcoded boundary.
      </div>

      {empty && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 text-center">
          <FileText size={28} className="mx-auto mb-3 text-brand-600" />
          <p className="text-sm font-semibold text-slate-800">No report configuration yet</p>
          <p className="text-xs text-slate-500 mt-1 mb-4">Create the standard Nursery (EYFS) / Primary / Secondary sections, provisional grading scales and a template each.</p>
          <button onClick={() => bootstrap.mutate(undefined as any)} disabled={bootstrap.isPending} className="btn-primary gap-2 mx-auto">
            {bootstrap.isPending ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />} Create standard setup
          </button>
        </div>
      )}

      {/* Templates */}
      <div>
        <h2 className="text-sm font-bold text-slate-800 mb-3">Report Templates</h2>
        <div className="space-y-3">
          {templates.length === 0 ? <p className="text-sm text-slate-400">No templates yet.</p> : templates.map((t: ReportTemplate) => (
            <TemplateRow key={t.id} template={t} scales={scales} canWrite={canWrite} />
          ))}
        </div>
      </div>

      {/* Scales */}
      <div>
        <h2 className="text-sm font-bold text-slate-800 mb-3">Grading Scales</h2>
        <div className="space-y-3">
          {scales.length === 0 ? <p className="text-sm text-slate-400">No scales yet.</p> : scales.map((sc: GradingScale) => (
            <ScaleRow key={sc.id} scale={sc} canWrite={canWrite} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TemplateRow({ template, scales, canWrite }: { template: ReportTemplate; scales: GradingScale[]; canWrite: boolean }) {
  const update = useUpdateTemplate();
  const [form, setForm] = useState({
    assessment_mode: template.assessment_mode,
    ca_weight: template.ca_weight ?? "",
    exam_weight: template.exam_weight ?? "",
    grading_scale_id: template.grading_scale_id ?? "",
  });
  const save = () => update.mutate({ id: template.id, data: {
    assessment_mode: form.assessment_mode,
    ca_weight: form.ca_weight === "" ? null : Number(form.ca_weight),
    exam_weight: form.exam_weight === "" ? null : Number(form.exam_weight),
    grading_scale_id: form.grading_scale_id || null,
  } });

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div><span className="text-sm font-bold text-slate-800">{template.section_name || "—"}</span><span className="ml-2 text-xs text-slate-400">{template.name}</span></div>
        {template.is_provisional && <span className="badge bg-amber-50 text-amber-700 border-amber-200">Provisional</span>}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div><label className="label">Mode</label><select value={form.assessment_mode} onChange={(e) => setForm({ ...form, assessment_mode: e.target.value })} className="input" disabled={!canWrite}><option value="descriptive">Descriptive (EYFS)</option><option value="numeric">Numeric</option><option value="hybrid">Hybrid</option></select></div>
        <div><label className="label">CA weight</label><input type="number" value={form.ca_weight} onChange={(e) => setForm({ ...form, ca_weight: e.target.value })} className="input" disabled={!canWrite} placeholder="e.g. 40" /></div>
        <div><label className="label">Exam weight</label><input type="number" value={form.exam_weight} onChange={(e) => setForm({ ...form, exam_weight: e.target.value })} className="input" disabled={!canWrite} placeholder="e.g. 60" /></div>
        <div><label className="label">Grading scale</label><select value={form.grading_scale_id} onChange={(e) => setForm({ ...form, grading_scale_id: e.target.value })} className="input" disabled={!canWrite}><option value="">— None —</option>{scales.filter((s) => s.scale_type === "numeric").map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
      </div>
      {canWrite && <div className="flex justify-end mt-3"><button onClick={save} disabled={update.isPending} className="btn-secondary gap-2 text-xs py-1.5">{update.isPending ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save</button></div>}
    </div>
  );
}

function ScaleRow({ scale, canWrite }: { scale: GradingScale; canWrite: boolean }) {
  const replace = useReplaceScaleBands();
  const [rows, setRows] = useState(scale.bands.map((b) => ({ grade: b.grade, min_score: b.min_score ?? "", max_score: b.max_score ?? "", remark: b.remark ?? "" })));
  const numeric = scale.scale_type === "numeric";
  const save = () => replace.mutate({ id: scale.id, bands: rows.map((r, i) => ({
    grade: r.grade, remark: r.remark || null, position: i,
    min_score: numeric && r.min_score !== "" ? Number(r.min_score) : null,
    max_score: numeric && r.max_score !== "" ? Number(r.max_score) : null,
  })) });

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div><span className="text-sm font-bold text-slate-800">{scale.name}</span><span className="ml-2 text-[10px] font-bold uppercase text-slate-400">{scale.scale_type}</span></div>
        {scale.is_provisional && <span className="badge bg-amber-50 text-amber-700 border-amber-200">Provisional</span>}
      </div>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-2">
            <input value={r.grade} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, grade: e.target.value } : x))} className="input w-24" placeholder="Grade" disabled={!canWrite} />
            {numeric && <><input type="number" value={r.min_score} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, min_score: e.target.value } : x))} className="input w-20" placeholder="min" disabled={!canWrite} /><span className="text-slate-400">&ndash;</span><input type="number" value={r.max_score} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, max_score: e.target.value } : x))} className="input w-20" placeholder="max" disabled={!canWrite} /></>}
            <input value={r.remark} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, remark: e.target.value } : x))} className="input flex-1" placeholder="Remark" disabled={!canWrite} />
            {canWrite && <button onClick={() => setRows(rows.filter((_, j) => j !== i))} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>}
          </div>
        ))}
      </div>
      {canWrite && (
        <div className="flex justify-between mt-3">
          <button onClick={() => setRows([...rows, { grade: "", min_score: "", max_score: "", remark: "" }])} className="btn-secondary gap-1.5 text-xs py-1.5"><Plus size={13} /> Add band</button>
          <button onClick={save} disabled={replace.isPending} className="btn-primary gap-2 text-xs py-1.5">{replace.isPending ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save &amp; lock numbers</button>
        </div>
      )}
    </div>
  );
}
