"use client";

import { useEffect, useMemo, useState } from "react";
import { useClasses, useCreateClass, useUpdateClass, useDeleteClass, useYearGroups, useTeachers } from "@/hooks/useSchool";
import { useSections } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Plus, X, Loader2, Pencil, Trash2, User, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import type { SchoolClass } from "@/types";

const CAT_LABEL: Record<string, string> = { active: "Active", alumni: "Alumni", prospective: "Prospective" };
type SortKey = "n" | "year_group" | "name" | "category" | "student_count";

export default function ManageClassPage() {
  const canWrite = useHasPermission("school:write");
  const { data: sections = [] } = useSections();
  const [schoolId, setSchoolId] = useState("");
  const [yearGroup, setYearGroup] = useState("");   // "" = All
  const [perPage, setPerPage] = useState(10);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "n", dir: 1 });
  const [form, setForm] = useState<null | { id?: string; name: string; year_group: string; capacity: string; class_teacher_id: string; academic_year: string }>(null);

  // Default to the first school (Early Years) once they load.
  const orderedSections = useMemo(() => [...sections].sort((a, b) => a.position - b.position), [sections]);
  useEffect(() => { if (!schoolId && orderedSections.length) setSchoolId(orderedSections[0].id); }, [orderedSections, schoolId]);
  const school = orderedSections.find((s) => s.id === schoolId);

  const { data: groups = [] } = useYearGroups(schoolId || undefined);
  const { data, isLoading } = useClasses({ section_id: schoolId || undefined, year_group: yearGroup || undefined, page_size: 200 });
  const items: SchoolClass[] = data?.items || (Array.isArray(data) ? data : []);
  const createClass = useCreateClass();
  const updateClass = useUpdateClass();
  const deleteClass = useDeleteClass();
  const { data: teacherData } = useTeachers({ page_size: 200 });
  const teachers: any[] = teacherData?.items ?? (Array.isArray(teacherData) ? teacherData : []);

  const onSchool = (id: string) => { setSchoolId(id); setYearGroup(""); setPage(1); };

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const numbered = items.map((c, i) => ({ c, n: i + 1 }));
    const filtered = q ? numbered.filter(({ c }) => [c.name, c.year_group, c.category, c.class_teacher_name].some((v) => (v ?? "").toLowerCase().includes(q))) : numbered;
    const val = (r: { c: SchoolClass; n: number }) =>
      sort.key === "n" ? r.n : sort.key === "year_group" ? (r.c.year_group ?? "") : sort.key === "name" ? r.c.name
        : sort.key === "category" ? (r.c.category ?? "") : r.c.student_count;
    return [...filtered].sort((a, b) => (val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0) * sort.dir);
  }, [items, search, sort]);
  const pages = Math.max(1, Math.ceil(rows.length / perPage));
  const cur = Math.min(page, pages);
  const shown = rows.slice((cur - 1) * perPage, cur * perPage);

  const sortBy = (key: SortKey) => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : 1 }));
  const Th = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th onClick={() => sortBy(k)} className="px-3 py-3 text-left text-[13px] font-extrabold text-slate-800 whitespace-nowrap cursor-pointer select-none border border-slate-200 bg-white">
      <span className="inline-flex items-center gap-1.5">{children}
        {sort.key === k ? (sort.dir === 1 ? <ChevronUp size={13} className="text-brand-600" /> : <ChevronDown size={13} className="text-brand-600" />) : <ChevronsUpDown size={13} className="text-slate-300" />}
      </span>
    </th>
  );

  const openNew = () => setForm({ name: "", year_group: yearGroup || "", capacity: "40", class_teacher_id: "", academic_year: "" });
  const openEdit = (c: SchoolClass) => setForm({ id: c.id, name: c.name, year_group: c.year_group || c.grade_level || "", capacity: String(c.capacity ?? 40), class_teacher_id: c.class_teacher_id || "", academic_year: c.academic_year || "" });
  const save = () => {
    if (!form || !form.name.trim()) return;
    const payload: any = {
      name: form.name.trim(), grade_level: form.year_group || null, capacity: parseInt(form.capacity) || 40,
      // null, not "": the API clears the assignment on a null, and teacher_id is a foreign key.
      class_teacher_id: form.class_teacher_id || null, academic_year: form.academic_year || null,
    };
    if (form.id) updateClass.mutate({ id: form.id, data: payload }, { onSuccess: () => setForm(null) });
    else createClass.mutate({ ...payload, section_id: schoolId || null }, { onSuccess: () => setForm(null) });
  };
  const remove = (c: SchoolClass) => {
    if (confirm(`Delete "${c.name}"? Classes that still have students can't be deleted.`)) deleteClass.mutate(c.id);
  };
  const saving = createClass.isPending || updateClass.isPending;
  const schoolName = school?.name ?? "";

  return (
    <div className="p-4 sm:p-8 max-w-6xl mx-auto">
      <nav className="flex flex-wrap items-center gap-x-2 text-sm font-bold text-slate-900 mb-5">
        <span>Home</span><span className="text-slate-300">•</span><span>Classes/YearGroups</span><span className="text-slate-300">•</span><span>Manage Class</span>
      </nav>

      <section className="rounded-lg border border-emerald-900/70 bg-white overflow-hidden mb-6">
        <h2 className="bg-emerald-800 text-white font-bold tracking-wide px-4 py-3 text-lg">Select School to View Classes</h2>
        <div className="p-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-extrabold uppercase tracking-widest text-slate-600 mb-2">Select School:</label>
            <select value={schoolId} onChange={(e) => onSchool(e.target.value)} className="input uppercase">
              {orderedSections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-extrabold uppercase tracking-widest text-slate-600 mb-2">Select Year Group:</label>
            <select value={yearGroup} onChange={(e) => { setYearGroup(e.target.value); setPage(1); }} className="input uppercase">
              <option value="">All</option>
              {groups.map((g) => <option key={g.id} value={g.name}>{g.name}</option>)}
            </select>
          </div>
        </div>
      </section>

      {canWrite && (
        <div className="flex justify-end mb-3">
          <button onClick={openNew} className="inline-flex items-center gap-2 rounded-md bg-cyan-500 hover:bg-cyan-600 text-white font-semibold px-4 py-2.5 text-sm"><Plus size={16} /> Create Class</button>
        </div>
      )}

      <section className="rounded-lg border border-emerald-900/70 bg-white overflow-hidden">
        <h2 className="bg-emerald-800 text-white font-bold tracking-wide px-4 py-3 text-lg uppercase">Class Information For {schoolName}</h2>
        <div className="p-4">
          <div className="flex items-center justify-between gap-3 mb-3 text-sm text-slate-500">
            <label className="flex items-center gap-2">
              <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }} className="input !w-auto !py-1 !px-2 text-xs">
                {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
              </select> records
            </label>
            <label className="flex items-center gap-2">Search:
              <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="input !w-32 sm:!w-48 !py-1" />
            </label>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse min-w-[760px]">
              <thead>
                <tr>
                  <Th k="n">ID</Th><Th k="year_group">Year Group</Th><Th k="name">Class Name</Th><Th k="category">Category</Th>
                  <Th k="student_count">No of Students</Th>
                  <th className="px-3 py-3 text-left text-[13px] font-extrabold text-slate-800 border border-slate-200 bg-white">PC Teacher</th>
                  <th className="border border-slate-200 bg-white w-28" />
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr><td colSpan={7} className="py-10 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></td></tr>
                ) : shown.length === 0 ? (
                  <tr><td colSpan={7} className="py-10 text-center text-slate-400">No classes found.</td></tr>
                ) : shown.map(({ c, n }, i) => (
                  <tr key={c.id} className={cn("align-top", i % 2 === 0 ? "bg-slate-50" : "bg-white")}>
                    <td className="px-3 py-4 border border-slate-200">{n}</td>
                    <td className="px-3 py-4 border border-slate-200 uppercase">{c.year_group || c.grade_level || "—"}</td>
                    <td className="px-3 py-4 border border-slate-200 uppercase font-medium">{c.name}</td>
                    <td className="px-3 py-4 border border-slate-200">{CAT_LABEL[c.category ?? "active"] ?? c.category}</td>
                    <td className="px-3 py-4 border border-slate-200">{c.student_count}</td>
                    <td className="px-3 py-3 border border-slate-200">
                      {(c.pc_teachers?.length ?? 0) > 0 ? (
                        <div className="flex flex-col gap-1.5 items-start">
                          {c.pc_teachers!.map((t) => (
                            <span key={t.id} className="inline-flex items-center gap-1.5 rounded bg-green-600 text-white text-sm px-3 py-1.5"><User size={13} /> {t.name}</span>
                          ))}
                        </div>
                      ) : <span className="text-xs font-semibold text-amber-700">No PC teacher</span>}
                    </td>
                    <td className="px-3 py-3 border border-slate-200">
                      {canWrite && (
                        <div className="flex flex-col gap-1.5">
                          <button onClick={() => openEdit(c)} className="inline-flex items-center justify-center gap-1.5 rounded bg-blue-500 hover:bg-blue-600 text-white text-xs font-semibold px-3 py-1.5"><Pencil size={12} /> Edit</button>
                          <button onClick={() => remove(c)} disabled={deleteClass.isPending} className="inline-flex items-center justify-center gap-1.5 rounded bg-red-500 hover:bg-red-600 text-white text-xs font-semibold px-3 py-1.5"><Trash2 size={12} /> Delete</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-center font-bold text-slate-800 mt-6 mb-3 text-sm">
            Showing {rows.length === 0 ? 0 : (cur - 1) * perPage + 1} to {Math.min(cur * perPage, rows.length)} of {rows.length} entries
          </p>
          {pages > 1 && (
            <div className="flex justify-center">
              <div className="inline-flex rounded border border-slate-300 overflow-hidden text-sm">
                <button onClick={() => setPage(Math.max(1, cur - 1))} className="px-3 py-1.5 text-slate-500 hover:bg-slate-50" aria-label="Previous">‹</button>
                {Array.from({ length: pages }, (_, k) => k + 1).map((p) => (
                  <button key={p} onClick={() => setPage(p)} className={cn("px-3 py-1.5 border-l border-slate-300", p === cur ? "bg-blue-600 text-white font-bold" : "text-blue-600 hover:bg-slate-50")}>{p}</button>
                ))}
                <button onClick={() => setPage(Math.min(pages, cur + 1))} className="px-3 py-1.5 border-l border-slate-300 text-slate-500 hover:bg-slate-50" aria-label="Next">›</button>
              </div>
            </div>
          )}
        </div>
      </section>

      {form && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setForm(null)}>
          <div onClick={(e) => e.stopPropagation()} className="bg-white w-full sm:max-w-lg rounded-t-2xl sm:rounded-xl max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between bg-emerald-800 text-white px-4 py-3">
              <h3 className="font-bold">{form.id ? "Edit Class" : `Create Class — ${schoolName}`}</h3>
              <button onClick={() => setForm(null)} aria-label="Close"><X size={18} /></button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="label">Year Group *</label>
                <select value={form.year_group} onChange={(e) => setForm({ ...form, year_group: e.target.value })} className="input uppercase">
                  <option value="">— Select —</option>
                  {groups.map((g) => <option key={g.id} value={g.name}>{g.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Class Name *</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={form.year_group ? `e.g. ${form.year_group} Amethyst` : "e.g. Year 10 Amethyst"} className="input" />
              </div>
              <div>
                <label className="label">PC Teacher (class teacher)</label>
                {/* The class teacher is load-bearing: only they (or an administrator) can open the
                    class in Reports View or submit its report for approval. */}
                <select value={form.class_teacher_id} onChange={(e) => setForm({ ...form, class_teacher_id: e.target.value })} className="input">
                  <option value="">— None —</option>
                  {teachers.map((t) => <option key={t.id} value={t.id}>{[t.first_name, t.last_name].filter(Boolean).join(" ") || t.email}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Capacity</label><input type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} className="input" /></div>
                <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} placeholder="2025/2026" className="input" /></div>
              </div>
              <div className="flex justify-end gap-3 pt-1">
                <button onClick={() => setForm(null)} className="btn-secondary">Cancel</button>
                <button onClick={save} disabled={saving || !form.name.trim()} className="btn-primary gap-2">
                  {saving && <Loader2 size={15} className="animate-spin" />}{form.id ? "Update" : "Create Class"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
