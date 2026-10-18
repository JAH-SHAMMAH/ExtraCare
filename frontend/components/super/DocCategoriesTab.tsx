"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { DocCategory } from "@/lib/api";
import { Panel, SaveBar, useStructEditor } from "@/components/super/shared";
import { cn } from "@/lib/utils";

const pill = (on: boolean, yes: string, no: string, tone: string) => (
  <span className={cn("px-2 py-0.5 rounded text-xs font-bold text-white", on ? tone : "bg-amber-500")}>{on ? yes : no}</span>
);

export function DocCategoriesTab({ server }: { server: DocCategory[] | undefined }) {
  const { value, edit, commit, dirty, saving } = useStructEditor<DocCategory[]>("doc_categories", server);
  const [name, setName] = useState("");
  const [q, setQ] = useState("");
  if (!value) return null;
  const rows = value.map((c, i) => ({ c, i })).filter(({ c }) => c.name.toLowerCase().includes(q.toLowerCase()));
  const patch = (i: number, p: Partial<DocCategory>) => edit(value.map((c, j) => (j === i ? { ...c, ...p } : c)));
  const add = () => {
    const n = name.trim();
    if (!n || value.some((c) => c.name.toLowerCase() === n.toLowerCase())) return;
    edit([...value, { name: n, admission_status: "not_required", required: false, active: true, medical: false }]);
    setName("");
  };
  return (
    <Panel title="Student Document Categories">
      <div className="flex flex-wrap gap-2 mb-4">
        <input className="input flex-1 min-w-[180px]" placeholder="New document category" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
        <button onClick={add} className="btn-primary gap-1"><Plus size={15} /> Add Doc. Category</button>
        <input className="input w-40" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead><tr className="text-left text-xs uppercase text-slate-500 border-b"><th className="p-2">S/N</th><th className="p-2">Category</th><th className="p-2">Admission status</th><th className="p-2">Required</th><th className="p-2">Status</th><th className="p-2">Medical</th><th className="p-2">Action</th></tr></thead>
          <tbody>
            {rows.map(({ c, i }, n) => (
              <tr key={c.name} className="border-b border-slate-100">
                <td className="p-2">{n + 1}</td>
                <td className="p-2 font-semibold uppercase">{c.name}</td>
                <td className="p-2"><button onClick={() => patch(i, { admission_status: c.admission_status === "required" ? "not_required" : "required" })}>{pill(c.admission_status === "required", "Required", "Not Required", "bg-sky-500")}</button></td>
                <td className="p-2"><button onClick={() => patch(i, { required: !c.required })} className="px-2 py-0.5 rounded border text-xs">{c.required ? "Required" : "Not Required"}</button></td>
                <td className="p-2"><button onClick={() => patch(i, { active: !c.active })}>{pill(c.active, "Active", "Inactive", "bg-sky-500")}</button></td>
                <td className="p-2"><button onClick={() => patch(i, { medical: !c.medical })}>{pill(c.medical, "Yes", "No", "bg-sky-500")}</button></td>
                <td className="p-2"><button onClick={() => edit(value.filter((_, j) => j !== i))} aria-label={`Delete ${c.name}`} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-500 text-white text-xs"><Trash2 size={12} /> Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SaveBar dirty={dirty} saving={saving} onSave={commit} label="Save Categories" />
    </Panel>
  );
}
