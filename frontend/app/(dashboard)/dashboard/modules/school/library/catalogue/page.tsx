"use client";

import { useRef, useState } from "react";
import { BookPlus, FileUp, Loader2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { schoolApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { type LibraryBookRow } from "@/hooks/useSchool";
import { CatalogueTab, AddBookDrawer, IssueLoanDrawer } from "../_components";

/** Library — Manage Catalogue. Full book management: add, import, remove, issue. */
export default function ManageCataloguePage() {
  const canWrite = useHasPermission("school:library:write");
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [issueTarget, setIssueTarget] = useState<LibraryBookRow | null>(null);

  const imp = useMutation({
    mutationFn: (file: File) => schoolApi.library.books.import(file),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ["library"] });
      const skipped = res?.errors?.length ? `, ${res.errors.length} skipped` : "";
      toast.success(`Imported ${res?.imported ?? 0} book(s)${skipped}.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Import failed."),
  });
  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => { const f = e.target.files?.[0]; if (f) imp.mutate(f); e.target.value = ""; };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">Manage Catalogue</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Catalogue</h1>
          <p className="text-slate-500 text-sm mt-0.5">Add, import, edit and remove titles in the collection.</p>
        </div>
        {canWrite && (
          <div className="flex items-center gap-2">
            <input ref={fileRef} type="file" accept=".csv,.xlsx,.docx,.pdf" className="hidden" onChange={onFile} />
            <button onClick={() => fileRef.current?.click()} disabled={imp.isPending} className="btn-secondary gap-2" title="CSV / Excel / Word / PDF — a Word/PDF must contain a table with header row (title, author, isbn, category, publisher, publication_year, shelf_location, total_copies, description)">
              {imp.isPending ? <Loader2 size={15} className="animate-spin" /> : <FileUp size={15} />} Import Book Catalogue
            </button>
            <button onClick={() => setAddOpen(true)} className="btn-primary gap-2"><BookPlus size={15} /> New Book Catalogue</button>
          </div>
        )}
      </div>

      <CatalogueTab manage={canWrite} onIssue={(book) => setIssueTarget(book)} />
      {addOpen && <AddBookDrawer onClose={() => setAddOpen(false)} />}
      {issueTarget && <IssueLoanDrawer book={issueTarget} onClose={() => setIssueTarget(null)} />}
    </div>
  );
}
