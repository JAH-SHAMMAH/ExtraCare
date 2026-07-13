"use client";

import { useState } from "react";
import {
  useSections, useCreateSection, useUpdateSection, useDeleteSection, useAutoMapSections,
} from "@/hooks/usePlatform";
import { Loader2, Trash2, Plus, Wand2, Save, ChevronUp, ChevronDown } from "lucide-react";
import type { SchoolSection } from "@/types";

/**
 * School Types — the managed school sections/divisions (Nursery / Primary /
 * Secondary). Covers Educare's "View School Types" (list + edit) and "Reorder
 * Schools" (the up/down controls; single-school reorders its divisions). Report
 * templates and grading scales live on the Report Config tab.
 */
export function SchoolSections({ canWrite }: { canWrite: boolean }) {
  const { data: sections = [], isLoading } = useSections();
  const create = useCreateSection();
  const reorder = useUpdateSection();
  const autoMap = useAutoMapSections();
  const [name, setName] = useState("");
  const [curriculum, setCurriculum] = useState("hybrid");

  if (isLoading) return <div className="py-16 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>;

  const sorted = [...sections].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

  // Reorder by swapping the two adjacent sections' positions (index-based so the
  // order is always well-defined even if stored positions weren't contiguous).
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= sorted.length) return;
    reorder.mutate({ id: sorted[i].id, data: { position: j } });
    reorder.mutate({ id: sorted[j].id, data: { position: i } });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs text-slate-400 max-w-2xl">Sections are your school divisions (Nursery / Primary / Secondary). A class&apos;s <strong>level</strong> maps to a section via its aliases; report templates and grading are set per section on the Report Config tab.</p>
        {canWrite && sections.length > 0 && (
          <button onClick={() => autoMap.mutate()} disabled={autoMap.isPending} className="btn-secondary gap-2 text-xs py-1.5 shrink-0" title="Link classes to sections by an exact normalized level match">
            {autoMap.isPending ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />} Auto-map classes
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {sorted.length === 0 ? <p className="p-4 text-sm text-slate-400">No sections yet. Add one below, or use Report Config → &ldquo;Create standard setup&rdquo;.</p> : sorted.map((s, i) => (
          <SectionRow key={s.id} section={s} canWrite={canWrite}
            onUp={i > 0 ? () => move(i, -1) : undefined}
            onDown={i < sorted.length - 1 ? () => move(i, 1) : undefined} />
        ))}
        {canWrite && (
          <div className="flex items-end gap-3 px-4 py-3">
            <div className="flex-1"><label className="label">Section name</label><input value={name} onChange={(e) => setName(e.target.value)} className="input" placeholder="e.g. Primary" /></div>
            <div><label className="label">Curriculum</label><select value={curriculum} onChange={(e) => setCurriculum(e.target.value)} className="input"><option value="eyfs">EYFS</option><option value="nigerian">Nigerian</option><option value="hybrid">Hybrid</option></select></div>
            <button onClick={() => name.trim() && create.mutate({ name: name.trim(), curriculum, position: sections.length }, { onSuccess: () => setName("") })} disabled={!name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add</button>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionRow({ section, canWrite, onUp, onDown }: { section: SchoolSection; canWrite: boolean; onUp?: () => void; onDown?: () => void }) {
  const update = useUpdateSection();
  const del = useDeleteSection();
  const [aliases, setAliases] = useState((section.aliases || []).join(", "));
  const dirty = aliases.trim() !== (section.aliases || []).join(", ");
  const saveAliases = () => update.mutate({ id: section.id, data: { aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean) } });

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {canWrite && (
            <div className="flex flex-col">
              <button onClick={onUp} disabled={!onUp} className="text-slate-300 hover:text-slate-600 disabled:opacity-30 leading-none"><ChevronUp size={14} /></button>
              <button onClick={onDown} disabled={!onDown} className="text-slate-300 hover:text-slate-600 disabled:opacity-30 leading-none"><ChevronDown size={14} /></button>
            </div>
          )}
          <div><span className="text-sm font-semibold text-slate-800">{section.name}</span><span className="ml-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">{section.curriculum}</span></div>
        </div>
        {canWrite && <button onClick={() => { if (confirm(`Delete section ${section.name}? Its template is removed and classes become unassigned.`)) del.mutate(section.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
      </div>
      <div className="flex items-center gap-2 mt-2 md:ml-6">
        <input value={aliases} onChange={(e) => setAliases(e.target.value)} disabled={!canWrite} className="input text-xs flex-1" placeholder="Level aliases, comma-separated (e.g. YEAR 1, YEAR 2, …)" />
        {canWrite && <button onClick={saveAliases} disabled={!dirty || update.isPending} className="btn-secondary gap-1.5 text-xs py-1.5 shrink-0">{update.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Save</button>}
      </div>
    </div>
  );
}
