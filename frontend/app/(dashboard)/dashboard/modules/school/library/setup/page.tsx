"use client";

import { useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  useLibrarySettings, useSaveLibrarySettings,
  useLibraryCategories, useCreateLibraryCategory, useDeleteLibraryCategory,
  useLibraryLocations, useCreateLibraryLocation, useDeleteLibraryLocation,
  type LibraryCategory, type LibraryLocation,
} from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Settings2, Loader2, Plus, Trash2, Save, Tag, MapPin, SlidersHorizontal } from "lucide-react";

type Tab = "general" | "categories" | "locations";
const TABS: { key: Tab; label: string; icon: any }[] = [
  { key: "general", label: "General Setup", icon: SlidersHorizontal },
  { key: "categories", label: "Book Category", icon: Tag },
  { key: "locations", label: "Library Locations", icon: MapPin },
];

export default function LibrarySetupPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const canWrite = useHasPermission("school:library:write");
  const tab = (params.get("tab") as Tab) || "general";
  const setTab = (t: Tab) => router.replace(`${pathname}?tab=${t}`, { scroll: false });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">Library Setup</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><Settings2 size={22} className="text-brand-600" /> Library Setup</h1>
        <p className="text-slate-500 text-sm mt-0.5">Borrowing rules, categories and shelf locations.</p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-slate-200 mb-6">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={cn("flex items-center gap-1.5 px-3 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors", tab === t.key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800")}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "general" && <GeneralTab canWrite={canWrite} />}
      {tab === "categories" && <CategoriesTab canWrite={canWrite} />}
      {tab === "locations" && <LocationsTab canWrite={canWrite} />}
    </div>
  );
}

function GeneralTab({ canWrite }: { canWrite: boolean }) {
  const { data: settings, isLoading } = useLibrarySettings();
  const save = useSaveLibrarySettings();
  const [form, setForm] = useState<any>(null);
  const current = form ?? settings ?? null;
  if (isLoading || !current) return <div className="py-12 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>;
  const patch = (p: any) => setForm({ ...current, ...p });

  return (
    <div className="max-w-xl space-y-4">
      <p className="text-sm text-slate-500">Borrowing rules apply when a book is issued &mdash; the loan period defaults the due date, and the per-member limit is the borrowing &ldquo;permission&rdquo;.</p>
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        <div className="flex items-center justify-between px-4 py-3.5"><div><p className="text-sm font-semibold text-slate-800">Loan period (days)</p><p className="text-xs text-slate-500">Default due date = today + this.</p></div><input type="number" min={1} max={365} value={current.loan_period_days} disabled={!canWrite} onChange={(e) => patch({ loan_period_days: Number(e.target.value) || 14 })} className="input w-24" /></div>
        <div className="flex items-center justify-between px-4 py-3.5"><div><p className="text-sm font-semibold text-slate-800">Max books per member</p><p className="text-xs text-slate-500">How many a member may hold at once.</p></div><input type="number" min={1} max={100} value={current.max_books_per_user} disabled={!canWrite} onChange={(e) => patch({ max_books_per_user: Number(e.target.value) || 1 })} className="input w-24" /></div>
        <label className="flex items-center justify-between px-4 py-3.5 cursor-pointer"><div><p className="text-sm font-semibold text-slate-800">Allow reviews</p><p className="text-xs text-slate-500">Members can review books they&apos;ve read.</p></div><input type="checkbox" checked={current.allow_reviews} disabled={!canWrite} onChange={(e) => patch({ allow_reviews: e.target.checked })} className="h-4 w-4 rounded border-slate-300" /></label>
        <label className="flex items-center justify-between px-4 py-3.5 cursor-pointer"><div><p className="text-sm font-semibold text-slate-800">Reviews need approval</p><p className="text-xs text-slate-500">A review stays hidden until a librarian approves it.</p></div><input type="checkbox" checked={current.review_needs_approval} disabled={!canWrite} onChange={(e) => patch({ review_needs_approval: e.target.checked })} className="h-4 w-4 rounded border-slate-300" /></label>
      </div>
      {canWrite && <div className="flex justify-end"><button onClick={() => save.mutate(current, { onSuccess: () => setForm(null) })} disabled={save.isPending || !form} className="btn-primary gap-2">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save settings</button></div>}
    </div>
  );
}

function CategoriesTab({ canWrite }: { canWrite: boolean }) {
  const { data: cats = [], isLoading } = useLibraryCategories();
  const create = useCreateLibraryCategory();
  const del = useDeleteLibraryCategory();
  const [name, setName] = useState("");
  const add = () => { if (name.trim()) create.mutate({ name: name.trim() }, { onSuccess: () => setName("") }); };

  return (
    <div className="max-w-lg">
      <p className="text-sm text-slate-500 mb-4">Managed book categories &mdash; these feed the catalogue&apos;s category picklist.</p>
      {canWrite && <div className="flex gap-2 mb-4"><input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} placeholder="New category" className="input" /><button onClick={add} disabled={create.isPending || !name.trim()} className="btn-primary gap-1.5 shrink-0"><Plus size={15} /> Add</button></div>}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {isLoading ? <div className="p-6 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" size={18} /></div>
          : cats.length === 0 ? <div className="p-6 text-center text-sm text-slate-400">No categories yet.</div>
            : cats.map((c: LibraryCategory) => (<div key={c.id} className="flex items-center gap-2 px-4 py-3"><Tag size={14} className="text-slate-400" /><span className="flex-1 text-sm font-medium text-slate-800">{c.name}</span>{canWrite && <button onClick={() => del.mutate(c.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</div>))}
      </div>
    </div>
  );
}

function LocationsTab({ canWrite }: { canWrite: boolean }) {
  const { data: locs = [], isLoading } = useLibraryLocations();
  const create = useCreateLibraryLocation();
  const del = useDeleteLibraryLocation();
  const [form, setForm] = useState({ name: "", code: "" });
  const add = () => { if (form.name.trim()) create.mutate({ name: form.name.trim(), code: form.code.trim() || undefined }, { onSuccess: () => setForm({ name: "", code: "" }) }); };

  return (
    <div className="max-w-lg">
      <p className="text-sm text-slate-500 mb-4">Managed shelves / locations &mdash; these feed the catalogue&apos;s shelf picklist.</p>
      {canWrite && <div className="flex gap-2 mb-4"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Aisle A — Fiction" className="input flex-1" /><input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="Code (A3)" className="input w-28" /><button onClick={add} disabled={create.isPending || !form.name.trim()} className="btn-primary gap-1.5 shrink-0"><Plus size={15} /> Add</button></div>}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {isLoading ? <div className="p-6 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" size={18} /></div>
          : locs.length === 0 ? <div className="p-6 text-center text-sm text-slate-400">No locations yet.</div>
            : locs.map((l: LibraryLocation) => (<div key={l.id} className="flex items-center gap-2 px-4 py-3"><MapPin size={14} className="text-slate-400" /><span className="flex-1 text-sm font-medium text-slate-800">{l.name}</span>{l.code && <span className="badge bg-slate-50 text-slate-600 border-slate-200 text-xs">{l.code}</span>}{canWrite && <button onClick={() => del.mutate(l.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</div>))}
      </div>
    </div>
  );
}
